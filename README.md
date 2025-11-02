# Texture Packer

A powerful Python tool for batch processing and packing game engine texture maps. Automatically converts textures from various sources (Textures.com, TextureHaven, etc.) with inconsistent naming and channel layouts into standardized formats required by game engines.

---

## Features

- **Preset Modes**: Quick ORM/ORD packing without config files
- **Unreal Engine Naming**: Industry-standard naming convention support
- **Validation Mode**: Check for missing textures before packing
- **Batch Processing**: Process multiple texture sets automatically
- **Game Engine Presets**: Unity and Unreal Engine workflows built-in
- **Format Support**: PNG, JPG, BMP, TGA, DDS
- **Channel Packing**: Flexible channel remapping and packing

---

## Installation

```bash
pip install pillow numpy
```

---

## Quick Start

### Basic ORM Packing
```bash
python texture_packer.py --preset orm -s ./textures -d ./output
```

### ORD Packing (with Height/Displacement)
```bash
python texture_packer.py --preset ord -s ./textures -d ./output
```

### With Unreal Engine Naming
```bash
python texture_packer.py --preset orm -s ./textures -d ./output --naming-scheme unreal
```

### With Validation
```bash
python texture_packer.py --preset orm -s ./textures -d ./output --validate
```

---

## How It Works

![Workflow Scheme](./_assets/Scheme.webp)

**Workflow**: Scan files → Remap suffixes → Group by name → Pack channels → Save

### File Naming Concepts

Files have 3 parts: **group name**, **suffix**, **extension**

Example: `Wood_Planks_Normal.png`
- Group name: `Wood_Planks`
- Suffix: `_Normal`
- Extension: `.png`

The tool:
1. Scans files with specified extensions and suffixes
2. Groups textures by name prefix
3. Packs channels according to configuration
4. Saves with new suffixes based on channel layout

---

## Available Presets

| Preset | Description | Output |
|--------|-------------|--------|
| `orm` | Standard PBR | Occlusion(R) + Roughness(G) + Metallic(B) |
| `ord` | With displacement | Occlusion(R) + Roughness(G) + Height(B) |
| `unity` | Unity Engine | Metallic-Smoothness workflow |
| `unreal` | Unreal Engine | ORM + separate height maps |

---

## Naming Schemes

### Standard Naming (default)
```bash
python texture_packer.py --preset orm -s ./textures -d ./output
# Output: wood_planks_albedo.png, wood_planks_orm.png, wood_planks_normal.png
```

### Unreal Engine Naming Convention
```bash
python texture_packer.py --preset orm -s ./textures -d ./output --naming-scheme unreal
# Output: T_WoodPlanks_D.png, T_WoodPlanks_ORM.png, T_WoodPlanks_N.png
```

**Unreal Naming Rules:**
- Prefix: `T_` for all textures
- Uppercase suffixes: `_D` (Diffuse), `_N` (Normal), `_ORM` (packed), etc.
- Base name preserved from input

**Unreal Suffix Reference:**
- `_D` - Diffuse/Albedo
- `_N` - Normal
- `_R` - Roughness
- `_O` - Ambient Occlusion
- `_M` - Metallic
- `_H` - Height/Displacement
- `_A` - Alpha/Opacity
- `_E` - Emissive
- `_S` - Specular
- `_ORM` - Packed: Occlusion-Roughness-Metallic
- `_ORD` - Packed: Occlusion-Roughness-Displacement

---

## Command-Line Options

```bash
python texture_packer.py [OPTIONS]

Required:
  -s, --src DIR            Source directory with textures
  -d, --dest DIR           Destination directory

Optional:
  -c, --config FILE        Config file path (default: config.txt)
  -o, --output-format FMT  Output format: png, jpg, bmp, tga, dds (default: png)
  -p, --preset PRESET      Preset: orm, ord, unity, unreal
  --pack-type TYPE         Alias for --preset (orm or ord)
  --naming-scheme SCHEME   Naming convention: standard, unreal (default: standard)
  --validate               Validate textures exist before packing
  --owerwrite             Overwrite existing files (default: true)
  --no-owerwrite          Don't overwrite existing files
  -h, --help              Show help message
```

---

## Usage Examples

### Example 1: Basic ORM Packing
```bash
python texture_packer.py --preset orm -s ./downloads/textures -d ./game/assets
```

### Example 2: ORD with Validation
```bash
python texture_packer.py --preset ord -s ./textures -d ./output --validate --no-owerwrite
```

### Example 3: Unreal Engine Workflow
```bash
python texture_packer.py --preset unreal -s ./source -d ./Content/Textures --naming-scheme unreal
```

### Example 4: Unity Workflow with BMP
```bash
python texture_packer.py --preset unity -s ./source -d ./Assets/Textures -o bmp
```

### Example 5: Custom Config
```bash
python texture_packer.py -c my_config.txt -s ./textures -d ./output
```

---

## Configuration File

Create a `config.txt` file for custom packing:

```ini
[settings]
src_dir > textures/input
dest_dir > textures/output
lowercase_names > true
output_format > png
owerwrite > true

[filters]
.png
.jpg
.tga
.bmp

[map suffixes]
# Map input suffixes to standard names
_color > _albedo
_base_color > _albedo
_ambient_occlusion > _ao
_albedo
_normal
_roughness
_metallic
_ao
_height

[pack]
# Define output textures and channel layout
# Format: _output_suffix > _source_suffix:channels | ...
_albedo > _albedo:rgb
_orm > _ao:r | _roughness:r | _metallic:r
_normal > _normal:rg*b
```

### Pack Section Syntax

`_result > _source1:channels | _source2:channels | ...`

- `>` - Separates output suffix from channel stack
- `|` - Pipeline separator for different source textures
- `:` - Separates source suffix from channel names
- `*` - Inverts channel (e.g., `rg*b` inverts blue channel)

**Examples:**
- `_orm > _ao:r | _roughness:r | _metallic:r` - Pack RGB from single channels
- `_normal > _normal:rg*b` - Copy RG, invert B (DX to GL conversion)
- `_albedo > _albedo:rgb | _alpha:r` - RGB from albedo, A from alpha

---

## Supported Input Suffixes

The tool recognizes these input suffixes:

**Albedo/Color:**
- `_albedo`, `_color`, `_base_color`, `_basecolor`, `_diffuse`

**Normal:**
- `_normal`

**Ambient Occlusion:**
- `_ao`, `_ambient_occlusion`, `_ambientocclusion`, `_occlusion`

**Roughness:**
- `_roughness`

**Metallic:**
- `_metallic`

**Height/Displacement:**
- `_height`, `_displacement`, `_disp`

**Other:**
- `_opacity`, `_alpha`, `_emissive`, `_specular`

**Unreal-style inputs** (lowercase):
- `_d`, `_n`, `_r`, `_o`, `_m`, `_a`, `_e`, `_s`

---

## Batch Processing

The tool automatically processes all texture sets in the source directory:

```bash
python texture_packer.py --preset orm -s ./my_textures -d ./output
```

**Input folder:**
```
my_textures/
├── Wood_Planks_Albedo.png
├── Wood_Planks_Normal.png
├── Wood_Planks_Roughness.png
├── Wood_Planks_AO.png
├── Wood_Planks_Metallic.png
├── Stone_Wall_Albedo.jpg
├── Stone_Wall_Normal.jpg
├── Stone_Wall_Roughness.jpg
├── Stone_Wall_AO.jpg
└── Stone_Wall_Metallic.jpg
```

**Output:**
```
output/
├── wood_planks_albedo.png
├── wood_planks_orm.png
├── wood_planks_normal.png
├── stone_wall_albedo.png
├── stone_wall_orm.png
└── stone_wall_normal.png
```

---

## Validation Mode

Use `--validate` to check for missing textures:

```bash
python texture_packer.py --preset orm -s ./textures -d ./output --validate
```

**What it does:**
- Checks all required textures exist for each set
- Lists missing textures
- Skips incomplete texture sets
- Shows available vs. required textures

**Example output:**
```
[!] Validation failed for 'Wood_Floor'
    Missing textures: _metallic, _roughness
    Available textures: _albedo, _normal, _ao
    Skipping this group...
```

---

## Config Examples

### ORM Preset Config
```ini
[settings]
src_dir > textures/src
dest_dir > textures/output
lowercase_names > true
output_format > png

[filters]
.png
.jpg
.tga
.bmp

[map suffixes]
_color > _albedo
_base_color > _albedo
_ambient_occlusion > _ao
_albedo
_normal
_roughness
_metallic
_ao

[pack]
_albedo > _albedo:rgb
_orm > _ao:r | _roughness:r | _metallic:r
_normal > _normal:rg*b
```

### ORD Preset Config
```ini
[pack]
_albedo > _albedo:rgb
_ord > _ao:r | _roughness:r | _height:r
_normal > _normal:rg*b
```

---

## Restrictions & Known Issues

**Restrictions:**
- All textures in the same group must be the same size
- No automatic up/downscaling support
- No recursive directory scanning

**Known Issues:**
- 16-to-8 bit grayscale conversion has minor histogram differences ([Pillow #3011](https://github.com/python-pillow/Pillow/issues/3011))

---

## Troubleshooting

### Textures Not Detected
- Check filename suffixes match supported patterns
- Use `--validate` to see what's missing
- Verify file extensions (.png, .jpg, .tga, .bmp)

### Empty Output Files
- Ensure source textures are valid images
- Check that suffix mappings are correct
- Verify texture sizes match within each group

### Wrong Packed Channels
- Verify you're using the correct preset (orm vs ord)
- Check custom config pack section if using config file

### Unreal Naming Issues
- Ensure `--naming-scheme unreal` is specified
- Base name casing is preserved from input files
- Use PascalCase for input names for best results

---

## License

MIT License - See LICENSE file for details

---

## Attribution

This enhanced version builds upon the original [texture-packer](https://github.com/raccoon-path/texture-packer) by [raccoon-path](https://github.com/raccoon-path).

**Original Author:** raccoon-path
**Original Repository:** https://github.com/raccoon-path/texture-packer

Enhancements include:
- Preset modes for common workflows
- Unreal Engine naming convention support
- Validation system
- Enhanced error handling
- BMP format support
- Comprehensive documentation
