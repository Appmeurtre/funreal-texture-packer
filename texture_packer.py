import argparse
import json
import string
import time
from os import error
from pathlib import Path
from xmlrpc.client import Boolean
from PIL.Image import Image
from PIL import Image as Img
from PIL import ImageChops
import numpy as np
from argparse import ArgumentParser

description = '''\
This texture packer is tool for batch renaming and packing images to textures with custom channel layout.
|Implemented:
    Packing images to texture channels,
    Remapping texture suffixes.
    Pack only unexisting output textures (optional).
    Preset modes for ORM and ORD packing.
    BMP texture format support.
|Not implemented:
    Recursive directory scanning, glob syntax,
'''

parser  = ArgumentParser(epilog = description)
parser.add_argument("-c","--config", dest="config", default="config.txt", help="Path to config (relative cwd or absolute). Default 'config.txt' in cwd")
parser.add_argument("-s", "--src", dest="src_dir", default=None, help="Path to directory with source textures (relative cwd or absolute)")
parser.add_argument("-d","--dest", dest="dest_dir", default=None, help="Path to destination directory (relative cwd or absolute)")
parser.add_argument("-o","--output-format", dest= "output_format", default=None, help="Output format", choices=["png","jpg","bmp","tga","dds"])
parser.add_argument("--owerwrite", type=bool, dest="owerwrite", action=argparse.BooleanOptionalAction, help = "Owerwrite already existing packed output textures.")
parser.add_argument("-p", "--preset", dest="preset", default=None, help="Use preset packing configuration", choices=["orm", "ord", "unity", "unreal"])
parser.add_argument("--pack-type", dest="pack_type", default=None, help="Alias for --preset (ORM or ORD packing)", choices=["orm", "ord"])
parser.add_argument("--validate", dest="validate", action="store_true", default=False, help="Validate that all required textures exist before packing")
parser.add_argument("--naming-scheme", dest="naming_scheme", default="standard", help="Naming convention to use", choices=["standard", "unreal"])
#parser.add_argument("-l","-local-config", dest= "local_config", action="store_true", default="false", help="Use local config (defined in -c or --config) in source directory")
args = parser.parse_args()


class FileGroups:dict[str,dict[str,str]]
''' FileGroups STRUCTURE:
groups{
    group_name:{
        _src_suffix:path,
        _src_suffix2:path2
        ...
    },
    group_name_2:{
        ...
    },
    ...
}
'''
class PackChItem:
    
    suffix:str = ""
    ch:int = 0
    invert:bool = False

    def __init__(self, _suffix:str, ch:int=0, invert:bool = False) -> None:
        self.suffix = _suffix
        self.ch = ch
        self.invert = invert
        pass


class Config:
    ASSIGN_SIGN = ">"
    CHANNEL_SEPARATOR = ":"
    PIPELINE_SEPARATOR = "|"
    CHANNEL_INVERSION_SIGN = "*"
    SECTION_OPEN_SIGN = "["
    SECTION_CLOSE_SIGN = "]"
    COMMENT_SIGN = "#"
    NUM_TO_CH = {
        0:"r",
        1:"g",
        2:"b",
        3:"a"
    }

    CH_TO_NUM = {
        "r":0,
        "g":1,
        "b":2,
        "a":3,
        "*":4
    }
    
    #This is default values for my texture packing pipeline for Godot (albedo, orm, gl_normal, height), all this params may be overriden from config file defined in -c --config param
    src_dir = "" #may be overriden from -s --src param
    dest_dir = "dest" #may be overriden from -d --dest param
    lowercase_names = False
    output_format = "png" #may be overriden -o --output-format param
    owerwrite = True #ADDED, True to preserve old bahavior
    naming_scheme = "standard" #can be "standard" or "unreal"
    extensions=[".png",".jpg",".tga"]

    # Unreal Engine naming convention mappings
    UNREAL_SUFFIX_MAP = {
        "_albedo": "_D",      # Diffuse/Albedo/Base Color
        "_normal": "_N",      # Normal
        "_roughness": "_R",   # Roughness
        "_ao": "_O",          # Ambient Occlusion
        "_metallic": "_M",    # Metallic
        "_height": "_H",      # Height/Displacement
        "_opacity": "_A",     # Alpha/Opacity
        "_emissive": "_E",    # Emissive
        "_specular": "_S",    # Specular
        "_mask": "_MASK",     # Mask
        "_orm": "_ORM",       # Packed: Occlusion-Roughness-Metallic
        "_ord": "_ORD",       # Packed: Occlusion-Roughness-Displacement
        "_rm": "_RM",         # Packed: Roughness-Metallic
        "_om": "_OM",         # Packed: Occlusion-Metallic
        "_nr": "_NR",         # Packed: Normal-Roughness
    }

    UNREAL_PREFIX = "T_"
    map_suffixes = {
        "_base_color":"_albedo",
        "_color":"_albedo",
        "_ambient_occlusion":"_ao",
        "_albedo":"",
        "_normal":"",
        "_ao":"",
        "_roughness":"",
        "_metallic":"",
        "_height":""
    }

    packer:dict[str:list[PackChItem]] = {
        "_albedo":[PackChItem("_albedo",0), PackChItem("_albedo",1),            PackChItem("_albedo",2)],
        "_orm":   [PackChItem("_ao"),       PackChItem("_roughness"),           PackChItem("_metallic")],
        "_normal":[PackChItem("_normal",0), PackChItem("_normal",1,invert=True),PackChItem("_normal",2)], 
    }

    

    def __init__(self) -> None:
        pass

    def apply_naming_scheme(self, base_name:str, suffix:str)->str:
        """
        Apply the configured naming scheme to a texture name.

        Args:
            base_name: The base texture name (e.g., "wood_planks")
            suffix: The texture suffix (e.g., "_albedo", "_orm")

        Returns:
            Formatted name according to naming scheme
        """
        if self.naming_scheme == "unreal":
            # Apply Unreal naming convention
            # Format: T_<BaseName><UnrealSuffix>
            # Convert standard suffix to Unreal suffix
            unreal_suffix = self.UNREAL_SUFFIX_MAP.get(suffix, suffix)

            # Clean base name: remove leading underscore if present, capitalize properly
            clean_base = base_name.lstrip('_')

            # Apply capitalization based on Unreal conventions
            # Base name uses PascalCase or keeps original casing
            # For simplicity, we'll preserve user's casing but ensure proper structure

            result = f"{self.UNREAL_PREFIX}{clean_base}{unreal_suffix}"

            # Don't apply lowercase_names for Unreal scheme (uses specific casing)
            return result
        else:
            # Standard naming scheme
            result = base_name + suffix
            if self.lowercase_names:
                result = result.lower()
            return result

    def apply_preset(self, preset_name:str):
        """Apply a preset packing configuration (orm, ord, unity, unreal)"""
        preset_name = preset_name.lower()

        # Common suffix mappings for all presets
        common_suffixes = {
            "_base_color": "_albedo",
            "_basecolor": "_albedo",
            "_color": "_albedo",
            "_diffuse": "_albedo",
            "_ambient_occlusion": "_ao",
            "_ambientocclusion": "_ao",
            "_occlusion": "_ao",
            "_displacement": "_height",
            "_disp": "_height",
            # Unreal-style input suffixes (for reading Unreal-named textures)
            "_d": "_albedo",  # T_Asset_D -> albedo
            "_n": "_normal",  # T_Asset_N -> normal
            "_r": "_roughness",  # T_Asset_R -> roughness
            "_o": "_ao",  # T_Asset_O -> AO
            "_m": "_metallic",  # T_Asset_M -> metallic (or mask, context-dependent)
            "_a": "_opacity",  # T_Asset_A -> opacity
            "_e": "_emissive",  # T_Asset_E -> emissive
            "_s": "_specular",  # T_Asset_S -> specular
            # Standard suffixes
            "_albedo": "",
            "_normal": "",
            "_ao": "",
            "_roughness": "",
            "_metallic": "",
            "_height": "",
            "_opacity": "",
            "_emissive": "",
            "_specular": ""
        }

        if preset_name == "orm":
            # ORM: Occlusion (R), Roughness (G), Metallic (B)
            print("[*] Applying ORM preset (Occlusion-Roughness-Metallic)")
            self.map_suffixes = common_suffixes
            self.packer = {
                "_albedo": [PackChItem("_albedo", 0), PackChItem("_albedo", 1), PackChItem("_albedo", 2)],
                "_orm": [PackChItem("_ao", 0), PackChItem("_roughness", 0), PackChItem("_metallic", 0)],
                "_normal": [PackChItem("_normal", 0), PackChItem("_normal", 1, invert=True), PackChItem("_normal", 2)],
            }

        elif preset_name == "ord":
            # ORD: Occlusion (R), Roughness (G), Displacement/Height (B)
            print("[*] Applying ORD preset (Occlusion-Roughness-Displacement)")
            self.map_suffixes = common_suffixes
            self.packer = {
                "_albedo": [PackChItem("_albedo", 0), PackChItem("_albedo", 1), PackChItem("_albedo", 2)],
                "_ord": [PackChItem("_ao", 0), PackChItem("_roughness", 0), PackChItem("_height", 0)],
                "_normal": [PackChItem("_normal", 0), PackChItem("_normal", 1, invert=True), PackChItem("_normal", 2)],
            }

        elif preset_name == "unity":
            # Unity: Metallic/Smoothness workflow (inverted roughness)
            print("[*] Applying Unity preset (Metallic-Smoothness)")
            self.map_suffixes = common_suffixes
            self.map_suffixes["_smoothness"] = ""
            self.packer = {
                "_albedo": [PackChItem("_albedo", 0), PackChItem("_albedo", 1), PackChItem("_albedo", 2)],
                "_metallic": [PackChItem("_metallic", 0), PackChItem("_ao", 0), PackChItem("_height", 0), PackChItem("_roughness", 0, invert=True)],
                "_normal": [PackChItem("_normal", 0), PackChItem("_normal", 1, invert=True), PackChItem("_normal", 2)],
            }

        elif preset_name == "unreal":
            # Unreal Engine: ORM + separate normal and height
            print("[*] Applying Unreal Engine preset")
            self.map_suffixes = common_suffixes
            self.packer = {
                "_albedo": [PackChItem("_albedo", 0), PackChItem("_albedo", 1), PackChItem("_albedo", 2)],
                "_orm": [PackChItem("_ao", 0), PackChItem("_roughness", 0), PackChItem("_metallic", 0)],
                "_normal": [PackChItem("_normal", 0), PackChItem("_normal", 1), PackChItem("_normal", 2)],
                "_height": [PackChItem("_height", 0)],
            }
        else:
            print(f"[!] Unknown preset: {preset_name}")
            return False

        return True

    def _split_trim(self, line:str, separator:str)->list[str]:
        return [itm.strip() for itm in line.split(separator)]
    
    def _get_sections(self, lines:list[str])->dict[str:list[str]]:
        sections:dict[str:list[str]]={}
        current_section = None
        for line in lines:
            if line == "" or line.isspace(): continue #skip empty lines
            if line.startswith(self.COMMENT_SIGN): continue #skip comments
            
            if line.startswith(self.SECTION_OPEN_SIGN) and line.endswith(self.SECTION_CLOSE_SIGN): #section change
                current_section = line[1:-1]
                content = sections.get(current_section,None)
                if content == None:
                    sections[current_section] = []
                continue
                
            if current_section == None: continue #skip line without section or comment
            sections[current_section].append(line)
        return sections

    def _convert_auto(self, s:str)->any:
        #auto type conversion, terrible implementation, but works perfectly for me, suitable for small params count
        v = s.strip().lower()
        #int
        try:
            return int(v)
        except:
            pass
        #float
        try:
            return float(v)
        except:
            pass
        #bool
        if v == "true" or v == "false":
            return v == "true"
        
        #str if any other conversions didn`t work
        return s
       
    def _parse_pack_ch_items(self, s:str)->list[PackChItem]:
        items = []
        suff, data,*_= s.split(self.CHANNEL_SEPARATOR)
        for i in range(len(data)):
            ch = self.CH_TO_NUM[data[i]]
            if ch < 4:
                items.append(PackChItem(suff,ch))
            elif ch == 4:
                p = items.pop()
                p.invert = True
                items.append(p)
        return items
    
    def _parse_mapstr(self, mapstr:str):
        result = []
        for p in self._split_trim(mapstr,self.PIPELINE_SEPARATOR):
            result.extend(self._parse_pack_ch_items(p))
        return result

    def _packer_ch_to_text(self, item:PackChItem)->str:
        return item.suffix + ":" + self.NUM_TO_CH[item.ch] + ("*" if item.invert else "")

    def override_params(self, data:any):
        if not type(data) == dict:
            try:
                data = data.__dict__
            except:
                return
        for k, v in data.items():
            if v != None and hasattr(self,k):
                setattr(self,k,v)

    def load_from_file(self, file:str|Path):
        if file is not Path:
            file = Path(file)
        lines = []
        try:
            lines = [ln.strip() for ln in file.read_text().splitlines()]
        except error:
            print("[!] Config file: "+str(file)+" not loaded")
            return self
        sect = self._get_sections(lines)
        
        #attributes
        st = {itm[0]: self._convert_auto(itm[1]) for itm in    [self._split_trim(x,self.ASSIGN_SIGN) for x in sect["settings"]]}
        self.override_params(st)
        
        #filters/extensions
        flt = sect["filters"]
        self.extensions = [ex.strip() for ex in flt]
        
        #map_suffixes
        m_suf = sorted(sect["map suffixes"], key = lambda x: len(x), reverse = True) #sort long>short to avoid partially replaced suffixes
        ms = {sf[0]:("" if len(sf) < 2 else sf[1]) for sf in    [self._split_trim(x, self.ASSIGN_SIGN) for x in m_suf]}
        
        self.map_suffixes = ms
        #parse packer map
        p_lines = sect["pack"]
        p_map={}
        for ln in p_lines:
            map_suff,map_data,*_ = self._split_trim(ln, self.ASSIGN_SIGN)
            p_map[map_suff] = self._parse_mapstr(map_data)
        self.packer = p_map

        return self

    def save_to_file(self, path:str|Path):
        data:list[str] = []
        data.append("[settings]")
        data.append("lowercase_names > "+str(self.lowercase_names))
        data.append("scan_subdirectories > "+str(self.scan_subdirectories))
        data.append("save_format > "+str(self.save_format))
        data.append("src_dir > "+str(self.src_dir))
        data.append("dest_dir > "+str(self.dest_dir))
        data.append("owerwrite >"+ str(self.owerwrite))
        data.append("[filters]")
        for itm in self.extensions:
            data.append(itm)
        
        data.append("[map suffixes]")
        for k, v in self.map_suffixes.items():
            data.append(k+("" if (v.isspace() or v == "") else " > "+ v))
        
        data.append("[pack]")
        for k,v in self.packer.items():
            s = k+" > " + self._packer_ch_to_text(v[0])
            
            if len(v)>1:
                for i in range(1,len(v)):
                    s+=" | " + self._packer_ch_to_text(v[i])
            data.append(s)
        if path is not Path:
            path = Path(path)
        path.write_text("\n".join(data))
       

        

class TexturePacker:
    
    SUFFIX_PLACEHOLDER = "@S@"
    
    IMG_MODES_MAP = {
        1:"L",
        3:"RGB",
        4:"RGBA"
    }

    def __init__(self) -> None:
        pass
    
    def convert_mode_i_to_l(self, img:Image)->Image:
        array = np.uint8(np.array(img) / 256)
        return Img.fromarray(array)

    def load_image(self, path:str)->Image:
        try:
            return Img.open(path)
        except error:
            print("[!] Image <"+str(path)+"> not loaded.")
            return None

    def get_file_suffix_index(self, name:str, suffixes:list[str] )-> tuple[str, int]:
        name = name.lower()
        for s in suffixes:
            # Check if suffix is at the end of the name (critical for short suffixes like _r, _n)
            if name.endswith(s):
                index = len(name) - len(s)
                return s, index
        return None, -1

    def get_mapped_suffix(self,suffix:str, suffix_map:dict[str,str])->str:
        mapped = suffix_map.get(suffix,"")
        return suffix if mapped == "" else mapped

    def get_groups(self, paths:list[Path], relative_to:Path, suffixes_map:dict[str,str])->dict[str,dict[str:Path]]:
        '''
        output:
        {
            group_name_1:{
                _suffix1:path1,
                ...,
                _suffix_n:path_n,
            },

            ...,

            group_name_n{
                ...
            }
        }
        '''
        # Sort suffixes by length (longest first) to prioritize specific matches over short ones
        suffixes = sorted(suffixes_map.keys(), key=lambda x: len(x), reverse=True)
        groups = {}
        for pth in paths:
            sf, sf_index = self.get_file_suffix_index(pth.stem,suffixes)

            if sf == None:
                print("[-] Skip: "+str(pth)+" (has no valid suffix, described in [map suffixes] section of config)")
                continue
            
            grp_name = str(pth.relative_to(relative_to)).rsplit(".",1)[0]
            grp_name = grp_name[ :sf_index] + self.SUFFIX_PLACEHOLDER + grp_name[sf_index + len(sf): ]
            
            itms = groups.get(grp_name, None)
            if itms == None:
                itms = {}
                groups[grp_name] = itms
            itms[self.get_mapped_suffix(sf,suffixes_map)] = pth
        return groups

    def get_filtered_packer_config(self, group_name:str, target_dir:Path)->dict[str, list[PackChItem]]:
        pk_conf = {}
        for pk_suffix in config.packer:
            excl_path = target_dir.joinpath(group_name + pk_suffix+"."+config.output_format)
            if not excl_path.exists():
                pk_conf[pk_suffix]=config.packer[pk_suffix]
            else:
                print("[-] Skip: " + str(excl_path) + " (file exists)")
        return pk_conf

    def load_texture_bands(self, group_items:dict[str,Path], config:dict[list[PackChItem]])->dict[str,list[Image]]:
        loaded:dict[str,list[Image]] = {}
        for pack_grp in config:
            pack_ch_itms = config[pack_grp]
            for pack_ch_itm in pack_ch_itms:
                band_path = group_items.get(pack_ch_itm.suffix, None)
                if band_path!=None and band_path.exists() and (loaded.get(pack_ch_itm.suffix, None) == None):
                    img = self.load_image(band_path)
                    if img != None:
                        loaded[pack_ch_itm.suffix] = img.split()
                    else:
                        loaded[pack_ch_itm.suffix] = None
        return loaded
    
    def pack_texture(self,band_lookup:dict[str,list[Image]], pack_items:list[PackChItem])->Image:
        if len(band_lookup) < 1:
            print("[!] Warning: No textures loaded for packing")
            return None

        # Find first valid band to determine size, filtering out None values
        valid_bands = [bands for bands in band_lookup.values() if bands is not None and len(bands) > 0]
        if len(valid_bands) == 0:
            print("[!] Warning: No valid texture bands found")
            return None

        black_ch = Img.new("L", valid_bands[0][0].size, 0) # Create black channel using first valid band size
        ch_bands:list[Image] = []

        for item in pack_items:
            g_tex = band_lookup.get(item.suffix, [])
            if g_tex is not None and item.ch<len(g_tex):
                bnd = g_tex[item.ch]
                if bnd is None:
                    print(f"[!] Warning: Band {item.ch} of {item.suffix} is None, using black channel")
                    ch_bands.append(black_ch)
                    continue

                if bnd.mode == "I":
                    #print("Item: "+item.suffix+" has I (32 bits per channel) format, convert to L(8 bits per channel).")
                    bnd = self.convert_mode_i_to_l(bnd)

                bnd = bnd if not item.invert else ImageChops.invert(bnd)
                ch_bands.append(bnd)
            else:
                print(f"[!] Warning: Texture {item.suffix} not found or channel {item.ch} missing, using black channel")
                ch_bands.append(black_ch)
            #print("-->: ["+item.suffix+"] contains "+str(len(g_tex))+" channels")

        if len(ch_bands)==0:
            print("[!] Warning: No channels to pack")
            return None

        if len(ch_bands)==2: #two channels unavailable, remove last one
            ch_bands.pop()
        img =  Img.merge(self.IMG_MODES_MAP[len(ch_bands)],ch_bands)
        return img

    def pack_material_stems(self, group_items:dict[str,Path], config:dict[str:list[PackChItem]]):
        packed_stems:dict[str,Image] = {}
        bands = self.load_texture_bands(group_items,config)
        for itm_name in config:
            #print("- texture: "+itm_name)
            tex = self.pack_texture(bands,config[itm_name])
            packed_stems[itm_name] = tex
        return packed_stems

    def validate_group(self, group_name:str, group_items:dict[str,Path], pack_config:dict[str:list[PackChItem]])->tuple[bool, list[str]]:
        """
        Validate that all required textures exist for a group.
        Returns (is_valid, list_of_missing_suffixes)
        """
        required_suffixes = set()
        for pack_items in pack_config.values():
            for pack_item in pack_items:
                required_suffixes.add(pack_item.suffix)

        missing = []
        for suffix in required_suffixes:
            if suffix not in group_items or not group_items[suffix].exists():
                missing.append(suffix)

        is_valid = len(missing) == 0
        return is_valid, missing

    def pack_textures(self, config:Config, validate:bool=False):
        
        src_dir = Path(config.src_dir).resolve()
        target_dir = Path(config.dest_dir).resolve()
        dest_is_src = src_dir == target_dir
        
        if not src_dir.exists():
            print("[!] Src directory <"+str(src_dir)+"> does not exists")
            exit(1)
        
        src_files = [fl for fl in src_dir.iterdir() if fl.suffix.lower() in config.extensions]

        groups = self.get_groups(src_files, src_dir, config.map_suffixes)

        print(f"[*] Found {len(groups)} texture group(s) to process")

        for grp_name in groups:
            # Filter pack items is (owerwrite==True)
            pk_conf = config.packer if config.owerwrite else self.get_filtered_packer_config(grp_name, target_dir)

            # Validate if requested
            if validate and pk_conf:
                is_valid, missing = self.validate_group(grp_name, groups[grp_name], pk_conf)
                if not is_valid:
                    print(f"[!] Validation failed for '{grp_name.replace(self.SUFFIX_PLACEHOLDER, '')}'")
                    print(f"    Missing textures: {', '.join(missing)}")
                    print(f"    Available textures: {', '.join(groups[grp_name].keys())}")
                    print("    Skipping this group...")
                    continue
                else:
                    print(f"[+] Validation passed for '{grp_name.replace(self.SUFFIX_PLACEHOLDER, '')}'")

            tex_lookup = self.pack_material_stems(groups[grp_name], pk_conf)
            
            t_dir = target_dir.joinpath(grp_name).parent
            if not t_dir.exists():
                print("[!] Directory <"+str(t_dir)+"> does not exists, create it..")
                t_dir.mkdir(parents=True)
            
            #save packed textures
            for tex_suffix in tex_lookup:
                # Get base name without placeholder
                base_name = grp_name.replace(self.SUFFIX_PLACEHOLDER, "")

                # Apply naming scheme (handles both standard and Unreal conventions)
                formatted_name = config.apply_naming_scheme(base_name, tex_suffix)

                # Create save path
                save_path = target_dir.joinpath(formatted_name + "." + config.output_format).resolve()

                #prevent silent overwrite sources
                if dest_is_src and save_path.exists():
                    print("[?] OVERWRITE SOURCE FILE: <"+str(save_path)+"> ?")
                    print(" -> [Y] [ENTER] to overwrite")
                    answ = input()
                    if answ.lower() !="y":
                        print("[!] Cancel")
                        continue

                if tex_lookup[tex_suffix] != None: #if output texture suffix described in config.packer but no source texture channels exists, <None> goes here, nasty bug fixed!
                    tex_lookup[tex_suffix].save(save_path,config.output_format) # finally, save the file
                    print("[+] Save: "+str(save_path))

if __name__ == "__main__":


    tmr = time.perf_counter()

    # Determine if using preset mode
    preset = args.preset or args.pack_type

    if preset:
        # Use preset configuration
        print(f"[*] Using preset mode: {preset.upper()}")
        config = Config()
        config.apply_preset(preset)
        # Override with command line args (except preset/pack_type)
        override_dict = {k: v for k, v in args.__dict__.items() if k not in ['preset', 'pack_type'] and v is not None}
        config.override_params(override_dict)
    else:
        # Use traditional config file mode
        config = Config().load_from_file(args.config)
        # Override config params from commandline
        config.override_params(args.__dict__)

    # Validate BMP support
    if ".bmp" not in config.extensions:
        config.extensions.append(".bmp")
        print("[*] Added .bmp to supported extensions")

    if config.owerwrite:
        print("[!] OWERWRITE mode: all output textures will be owerwritten.")
    else:
        print("[!] NO-OWERWRITE mode: existing files will not owerwritten")

    if args.validate:
        print("[*] VALIDATION mode: will check for missing textures")

    packer = TexturePacker()
    packer.pack_textures(config, validate=args.validate)


    tmr = round((time.perf_counter()-tmr))
    print("Texture packing complete. Elapsed time: "+str(tmr) + " s")

