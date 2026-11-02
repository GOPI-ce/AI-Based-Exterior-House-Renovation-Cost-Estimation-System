"""Generates app/data/catalog.json, the material catalogue (rates, coverage, palettes, site items, cities).

    python -m scripts.build_catalog

Rates are indicative 2026 figures excluding GST, researched from published MRPs, dealer listings and
Ahmedabad contractor rates, each with a low-high range. Edit the values here, regenerate, and commit both files.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "app" / "data" / "catalog.json"

EXTERIOR = {
    "Whites": [("Chalk White", "#F4F2EC"), ("Swan White", "#F1EFE7"), ("Pearl Mist", "#ECE9E1"), ("Lily White", "#F3F0E6"), ("Linen", "#EEE8DB"), ("Porcelain", "#E9E7E1"), ("Cloud Grey White", "#E4E3DE"), ("Snow Drift", "#F6F5F0"), ("Ivory Lace", "#F0EADA"), ("Rice Paper", "#EFEADF"), ("Moonbeam", "#E8E6DF"), ("Milk Glass", "#F2F1EB")],
    "Creams & ivories": [("Ivory White", "#EDE4D3"), ("Vanilla Cream", "#F1E5C9"), ("Buttermilk", "#F2E3BE"), ("Almond", "#EADBC3"), ("Cashew", "#E7D6B8"), ("Parchment", "#E9DEC6"), ("Custard", "#F0DDA9"), ("Champagne Cream", "#E8D9BC"), ("Honey Milk", "#EED8AE"), ("Biscuit", "#E2CCA6"), ("Wheat Field", "#E5D0A4"), ("Soft Ochre", "#E4CC98")],
    "Beiges & sands": [("Sandstone Beige", "#D9C4A2"), ("Desert Sand", "#D4BC97"), ("Jaisalmer Sand", "#D8BE8E"), ("Camel", "#C8AA7E"), ("Oat", "#D6C7AE"), ("Warm Taupe", "#A8927C"), ("Mushroom", "#B9A995"), ("Khaki Stone", "#BBA987"), ("Latte", "#C4A889"), ("Driftwood", "#B4A18A"), ("Pebble Beach", "#C9BBA6"), ("Dune", "#CDB28C")],
    "Browns & earth": [("Cocoa", "#6E5040"), ("Walnut Shell", "#7A5A44"), ("Coffee Bean", "#5B4334"), ("Chestnut", "#8A5A3C"), ("Clay Pot", "#9C6B4E"), ("Mud Brown", "#7F6650"), ("Cinnamon", "#9A6544"), ("Teak Brown", "#8C5E3C"), ("Hazel", "#A07A58"), ("Bark", "#5E4A3B"), ("Mocha", "#7B6352"), ("Umber", "#6A4E3A")],
    "Terracotta & reds": [("Terracotta", "#B4643F"), ("Burnt Sienna", "#A9583A"), ("Brick Red", "#9E4A36"), ("Rust", "#A65A33"), ("Clay Red", "#B0624A"), ("Maroon", "#6E2E2B"), ("Indian Red", "#A04A40"), ("Coral Clay", "#C47A5E"), ("Sindoor", "#B2402F"), ("Rosewood", "#874A44"), ("Pale Terracotta", "#CC8E6E"), ("Dusty Rose", "#C29A8B")],
    "Yellows & oranges": [("Mustard", "#CFA03C"), ("Turmeric", "#D6A637"), ("Marigold", "#DE9F3A"), ("Saffron", "#D98A3B"), ("Mango Lassi", "#E7B865"), ("Golden Wheat", "#D9B26A"), ("Amber", "#C98E3F"), ("Sunlit Yellow", "#E8C36A"), ("Lemon Chiffon", "#EFDB95"), ("Apricot", "#E1A87A"), ("Peach Sand", "#E6BE9C"), ("Ochre", "#B9883E")],
    "Greens": [("Sage Green", "#9DAE8F"), ("Olive Grove", "#7F8758"), ("Moss", "#6F7A55"), ("Pista", "#B9C59A"), ("Mint Leaf", "#A7C2AB"), ("Eucalyptus", "#8FA596"), ("Forest", "#4C5E48"), ("Bottle Green", "#3E5547"), ("Celadon", "#B6C7B0"), ("Fern", "#7E9670"), ("Sea Green", "#6F9488"), ("Neem", "#5F7350")],
    "Blues": [("Ocean Blue", "#4F7090"), ("Indigo Night", "#2F3E59"), ("Denim", "#566F8C"), ("Powder Blue", "#B5C6D3"), ("Sky Haze", "#A9BED0"), ("Steel Blue", "#5E7A92"), ("Teal Lagoon", "#3F6E73"), ("Peacock", "#2F5E66"), ("Slate Blue", "#6B7F93"), ("Navy", "#2A3449"), ("Aqua Mist", "#A9C7C5"), ("Dusk Blue", "#7D8FA6")],
    "Greys": [("Slate Grey", "#6C7176"), ("Dove Grey", "#B3B2AC"), ("Silver Fog", "#C7C8C4"), ("Ash", "#A3A29C"), ("Pewter", "#8C8D88"), ("Concrete", "#9E9C95"), ("Stone Grey", "#9A9890"), ("Warm Grey", "#A69E94"), ("Greige", "#B7AFA3"), ("Smoke", "#7E7F7B"), ("Elephant Grey", "#77746E"), ("Fossil", "#B9B4AA")],
    "Charcoals & darks": [("Charcoal", "#3C4044"), ("Graphite", "#55585B"), ("Gunmetal", "#4A4F53"), ("Onyx", "#2C2E30"), ("Basalt", "#3F3D3A"), ("Iron", "#4E4C49"), ("Ebony", "#2E2A27"), ("Midnight", "#262B33"), ("Anthracite", "#383B3D"), ("Soot", "#323232"), ("Deep Olive", "#3F4234"), ("Espresso", "#3B2F28")],
}

palettes = {
    "exterior": [{"name": n, "hex": h, "family": f} for f, items in EXTERIOR.items() for n, h in items],
    "metal": [{"name": n, "hex": h, "family": "Enamel"} for n, h in [("Deep Teal", "#2F3A3F"), ("Jet Black", "#1F2022"), ("Bronze Brown", "#5B3F2C"), ("Smoke Grey", "#7A7F84"), ("Ivory", "#E8E0CF"), ("Bus Green", "#2E4A3A"), ("Royal Blue", "#2B4A7A"), ("Signal Red", "#8E2A23"), ("Silver", "#B7BBBE"), ("Golden Brown", "#8A6234")]],
    "acp": [{"name": n, "hex": h, "family": f} for n, h, f in [("Charcoal Grey", "#3A3D40", "Solid"), ("Signal White", "#EFEFEC", "Solid"), ("Champagne", "#C9B48E", "Metallic"), ("Metallic Silver", "#B8BCBF", "Metallic"), ("Bronze", "#6E5440", "Metallic"), ("Jet Black", "#222426", "Solid"), ("Copper", "#9A5B3A", "Metallic"), ("Grey Blue", "#5B6B78", "Solid"), ("Ivory", "#E6DFCD", "Solid"), ("Brushed Gold", "#B8975A", "Metallic")]],
    "hpl": [{"name": n, "hex": h, "family": f} for n, h, f in [("Teak Wood", "#9A6236", "Wood"), ("Walnut", "#6B4429", "Wood"), ("Oak", "#B9844F", "Wood"), ("Concrete Grey", "#8E8C86", "Solid"), ("Anthracite", "#3A3C3E", "Solid"), ("Sand Beige", "#CDB896", "Solid"), ("Terracotta", "#A8603F", "Solid"), ("Off White", "#E9E6DF", "Solid")]],
    "wpc": [{"name": n, "hex": h, "family": "Wood"} for n, h in [("Teak", "#9A6236"), ("Walnut", "#6B4429"), ("Wenge", "#3E2B22"), ("Honey Oak", "#B9844F"), ("Ash Grey", "#8E8A83"), ("Coffee", "#5A3D2B")]],
    "texture": [{"name": n, "hex": h, "family": "Texture"} for n, h in [("Sand", "#D8CBB4"), ("Stone Grey", "#9A9890"), ("Ochre", "#C79A57"), ("Clay", "#B07B5E"), ("Graphite", "#55585B"), ("Ivory", "#E6DCC6"), ("Sage", "#A3AE95"), ("Terracotta", "#B4704F")]],
}

PAINT_SUITS = ["wall", "parapet", "pillar", "balcony", "roof_edge"]
PAINT_RENDER = {"mode": "tint", "texture": "plaster-fine.jpg", "tile_ft": 6, "strength": 0.15}


def paint(id, brand, product, tier, rate, rng, coverage, labour, lrng, warranty, pros, cons, maintenance, basecoat=None, durability=None):
    m = {
        "id": id, "name": f"{brand} {product}", "brand": brand, "product": product, "tier": tier,
        "category": "Exterior paint", "calc": "paint",
        "rate": rate, "rate_range": rng, "rate_unit": "L",
        "labour_rate": labour, "labour_range": lrng, "labour_unit": "sqft",
        "waste_pct": 5, "coverage_sqft_per_l_per_coat": coverage,
        "primer_coverage_sqft_per_l": 100, "primer_rate": 190, "pack_sizes_l": [20, 10, 4, 1],
        "warranty_years": warranty, "durability": durability or (f"{warranty}+ years" if warranty else "5-7 years"),
        "maintenance": maintenance, "pros": pros, "cons": cons,
        "suitable_for": PAINT_SUITS, "render": PAINT_RENDER, "palette": "exterior", "default_color": "#EDE4D3",
        "specs": [f"Practical coverage ~{coverage} sqft/L per coat on primed plaster", "System: 1 coat exterior primer + top coats"],
    }
    if basecoat:
        m["basecoat_rate"], m["basecoat_coverage_sqft_per_l"] = basecoat
        m["specs"][1] = "System: 1 coat primer + 1 coat elastomeric base coat + top coats"
    return m


def area(id, name, category, calc, rate, rng, labour, lrng, waste, render, suits, durability, maintenance, pros, cons, specs, brand=None, tier="standard", palette=None, default_color=None, **extra):
    m = {"id": id, "name": name, "brand": brand, "product": None, "tier": tier, "category": category, "calc": calc,
         "rate": rate, "rate_range": rng, "rate_unit": extra.pop("rate_unit", "sqft"),
         "labour_rate": labour, "labour_range": lrng, "labour_unit": extra.pop("labour_unit", "sqft"),
         "waste_pct": waste, "warranty_years": extra.pop("warranty_years", None), "durability": durability,
         "maintenance": maintenance, "pros": pros, "cons": cons, "suitable_for": suits, "render": render,
         "palette": palette, "default_color": default_color, "specs": specs}
    m.update(extra)
    return m


CLAD = ["wall", "pillar", "parapet", "balcony"]
materials = [
    # --- Paint systems (indicative dealer prices ex-GST, 20 L packs) -------------------------------------
    paint("ap_ace", "Asian Paints", "Ace Exterior Emulsion", "economy", 230, [200, 270], 80, 13, [10, 16], 3,
          ["Lowest cost", "Good for rental/compound walls"], ["Shorter life, fades sooner", "Limited dirt resistance"],
          "Repaint in about 4-5 years."),
    paint("ap_apex", "Asian Paints", "Apex Weatherproof Emulsion", "standard", 340, [300, 390], 90, 14, [11, 17], 5,
          ["Proven weatherproof emulsion", "Good value"], ["Average dirt pick-up resistance"], "Wash yearly; repaint in about 6 years."),
    paint("ap_apex_ultima", "Asian Paints", "Apex Ultima", "premium", 480, [430, 560], 100, 15, [12, 18], 7,
          ["Better sheen and colour retention", "Anti-algal"], ["Higher cost"], "Wash yearly; repaint in about 7-8 years."),
    paint("ap_ultima_protek", "Asian Paints", "Apex Ultima Protek (system)", "luxury", 560, [520, 620], 110, 18, [15, 22], 10,
          ["Elastomeric base coat bridges hairline cracks", "Longest-life system"], ["Most expensive", "Needs trained applicators"],
          "Wash yearly; long repaint cycle (10+ years claimed).", basecoat=(420, 80), durability="10-15 years (claimed)"),
    paint("berger_weathercoat_ll", "Berger", "WeatherCoat Long Life", "premium", 440, [400, 520], 100, 15, [12, 18], None,
          ["Strong weather resistance", "Wide colour range"], ["Warranty terms vary by variant"], "Wash yearly; repaint in about 7 years."),
    paint("nerolac_excel_total", "Nerolac", "Excel Total", "premium", 420, [380, 500], 100, 15, [12, 18], None,
          ["All-in-one weather protection", "Good dirt resistance"], ["Warranty terms vary by variant"], "Wash yearly; repaint in about 7 years."),
    paint("dulux_weathershield_max", "Dulux", "Weathershield Max", "premium", 500, [450, 580], 105, 15, [12, 18], None,
          ["High dirt and algae resistance", "Good colour retention"], ["Premium price"], "Wash yearly; repaint in about 8 years."),
    # --- Textures & coatings ----------------------------------------------------------------------------
    area("texture_roller", "Textured coating (roller / scratch)", "Texture & special finishes", "texture", 45, [38, 60], 22, [18, 30], 8,
         {"mode": "tint", "texture": "concrete-smooth.jpg", "tile_ft": 4, "strength": 0.55}, CLAD,
         "8-10 years", "Top coat can be renewed without redoing the texture.", ["Hides surface imperfections", "Premium look at moderate cost"],
         ["Collects dust in rough patterns"], ["~0.15 kg/sqft", "Finished with 2 coats of exterior emulsion"],
         palette="texture", default_color="#D8CBB4", rate_unit="kg", kg_per_sqft=0.15, bag_kg=25),
    area("stone_spray", "Spray stone-finish coating (granite look)", "Texture & special finishes", "area", 55, [45, 80], 28, [22, 35], 7,
         {"mode": "texture", "texture": "granite.jpg", "tile_ft": 3}, CLAD, "10-12 years", "Wash occasionally.",
         ["Stone look at a fraction of the weight", "Seamless"], ["Spray equipment and skilled crew needed"], ["Sprayed in 2-3 mm"], tier="premium"),
    area("microcement", "Exposed-concrete (microcement) finish", "Texture & special finishes", "area", 120, [100, 160], 70, [55, 90], 7,
         {"mode": "texture", "texture": "concrete-smooth.jpg", "tile_ft": 6}, CLAD + ["roof_edge"], "10-15 years", "Reseal every 2-3 years.",
         ["Seamless industrial look"], ["Hairline cracks can show"], ["2-3 mm trowelled layers + sealer"], tier="premium"),
    # --- Natural stone cladding (supply ex-GST, 20-25 mm, fixed with stone adhesive) --------------------
    area("stone_jaisalmer", "Jaisalmer yellow sandstone (natural split)", "Stone cladding", "cladding", 140, [110, 180], 75, [60, 90], 10,
         {"mode": "texture", "texture": "stone-sandstone.jpg", "tile_ft": 4.5, "tint": "#F0D9A8"}, CLAD, "25+ years",
         "Seal every 3-4 years to avoid staining.", ["Warm golden tone", "Very long life"], ["Porous: needs sealing", "Heavy"],
         ["20-25 mm natural split strips", "Fixed with polymer stone adhesive"], adhesive_sqft_per_bag=30, adhesive_rate=480, tier="premium"),
    area("stone_dholpur", "Dholpur beige sandstone", "Stone cladding", "cladding", 115, [90, 140], 70, [60, 85], 10,
         {"mode": "texture", "texture": "stone-sandstone.jpg", "tile_ft": 5, "tint": "#E9DCC6"}, CLAD, "25+ years",
         "Seal every 3-4 years.", ["Soft neutral beige", "Classic heritage look"], ["Shows dirt if unsealed"], ["20-25 mm cladding strips"],
         adhesive_sqft_per_bag=30, adhesive_rate=480),
    area("stone_kota", "Kota blue limestone", "Stone cladding", "cladding", 65, [55, 85], 65, [55, 80], 8,
         {"mode": "texture", "texture": "kota.jpg", "tile_ft": 6}, CLAD, "25+ years", "Low maintenance; occasional wash.",
         ["Economical natural stone", "Durable, cool grey-blue"], ["Plain look unless textured"], ["Cut panels, 20-25 mm"],
         adhesive_sqft_per_bag=35, adhesive_rate=480, tier="economy"),
    area("stone_slate", "Multicolour slate cladding", "Stone cladding", "cladding", 90, [70, 120], 75, [60, 90], 10,
         {"mode": "texture", "texture": "stone-grey.jpg", "tile_ft": 5}, CLAD, "25+ years", "Wash occasionally; joints can trap dirt.",
         ["Rich layered colours", "Rustic texture"], ["Flaky edges need careful fixing"], ["Natural split strips"],
         adhesive_sqft_per_bag=30, adhesive_rate=480),
    area("stone_ledge", "Ledge-stone panels (stacked, charcoal)", "Stone cladding", "cladding", 190, [160, 240], 70, [60, 85], 8,
         {"mode": "texture", "texture": "stone-sandstone.jpg", "tile_ft": 4, "tint": "#8A8580"}, CLAD, "25+ years",
         "Low maintenance.", ["Dramatic stacked-stone look", "Fast to install as panels"], ["Premium price"], ["Interlocking 150 x 600 mm panels"],
         adhesive_sqft_per_bag=30, adhesive_rate=480, tier="luxury"),
    area("granite_cladding", "Granite cladding (flamed, grey)", "Stone cladding", "cladding", 180, [150, 250], 90, [75, 110], 8,
         {"mode": "tiles", "texture": "granite.jpg", "tile_ft": 4, "joint_w_ft": 2, "joint_h_ft": 1}, CLAD, "30+ years",
         "Practically maintenance-free.", ["Hardest-wearing option", "Stain resistant"], ["Heaviest; needs mechanical clamps above ground floor"],
         ["18-20 mm flamed slabs 600 x 300 mm"], adhesive_sqft_per_bag=25, adhesive_rate=520, tier="luxury"),
    # --- Tiles (GVT, ex-GST) ----------------------------------------------------------------------------
    area("gvt_300x600", "GVT elevation tiles 300 x 600 mm (stone look)", "Elevation tiles", "tiles", 55, [45, 70], 45, [38, 55], 8,
         {"mode": "tiles", "texture": "travertine.jpg", "tile_ft": 6, "joint_w_ft": 2, "joint_h_ft": 1, "tint": "#D9D3C8"}, CLAD,
         "20+ years", "Wipe clean; check grout every few years.", ["Easy to clean", "Doesn't fade"], ["Grid look can feel busy"],
         ["Glazed vitrified, 8-9 mm"], tile_w_ft=1.97, tile_h_ft=0.98, tiles_per_box=8, adhesive_sqft_per_bag=40, adhesive_rate=480),
    area("gvt_600x1200", "GVT elevation tiles 600 x 1200 mm (travertine look)", "Elevation tiles", "tiles", 90, [70, 120], 55, [45, 70], 8,
         {"mode": "tiles", "texture": "travertine.jpg", "tile_ft": 8, "joint_w_ft": 3.94, "joint_h_ft": 1.97}, CLAD,
         "20+ years", "Wipe clean; check edge adhesion.", ["Large seamless look", "Premium finish"], ["Needs skilled fixing at height", "Heavier panels"],
         ["Glazed vitrified, 9-10 mm"], tile_w_ft=3.94, tile_h_ft=1.97, tiles_per_box=2, adhesive_sqft_per_bag=35, adhesive_rate=480, tier="premium"),
    area("tile_wood_finish", "Wood-finish elevation tiles 200 x 1200 mm", "Elevation tiles", "tiles", 75, [60, 100], 55, [45, 70], 10,
         {"mode": "tint", "texture": "wood-siding.jpg", "tile_ft": 6, "strength": 0.9}, CLAD, "20+ years", "Wipe clean.",
         ["Wood look with tile durability", "No termites, no fading"], ["Joints visible up close"], ["Glazed vitrified planks"],
         palette="wpc", default_color="#9A6236", tile_w_ft=3.94, tile_h_ft=0.66, tiles_per_box=6, adhesive_sqft_per_bag=40, adhesive_rate=480),
    area("brick_tiles", "Clay brick cladding tiles (wire-cut)", "Elevation tiles", "cladding", 95, [80, 140], 55, [45, 70], 8,
         {"mode": "texture", "texture": "brick-red.jpg", "tile_ft": 4.5}, ["wall", "pillar", "parapet"], "25+ years",
         "Apply water-repellent every 3-5 years.", ["Classic exposed-brick look", "Lighter than full bricks"], ["Can effloresce without sealing"],
         ["15-20 mm clay slips"], adhesive_sqft_per_bag=35, adhesive_rate=480),
    # --- Panels (supply ex-GST + fitting incl. framework) ------------------------------------------------
    area("acp_pvdf", "ACP 4 mm PVDF (standard core)", "Cladding panels", "sheet", 150, [130, 220], 150, [120, 200], 12,
         {"mode": "panel", "joint_w_ft": 4, "joint_h_ft": 8}, ["wall", "parapet", "roof_edge", "pillar", "balcony"], "15-20 years",
         "Wash twice a year; check sealant joints.", ["Sharp contemporary look", "Lightweight"], ["Not fire rated: avoid on escape routes"],
         ["4 mm, 0.25 mm aluminium skins, PVDF coat", "Aluminium sub-frame + silicone joints"], sheet_sqft=32, palette="acp", default_color="#3A3D40"),
    area("acp_fr", "ACP 4 mm PVDF fire-retardant (FR core)", "Cladding panels", "sheet", 230, [200, 300], 160, [130, 210], 12,
         {"mode": "panel", "joint_w_ft": 4, "joint_h_ft": 8}, ["wall", "parapet", "roof_edge", "pillar", "balcony"], "15-20 years",
         "Wash twice a year.", ["Fire-retardant core (safer)", "Same modern look"], ["Costlier than standard ACP"],
         ["FR mineral core", "Aluminium sub-frame"], sheet_sqft=32, palette="acp", default_color="#C9B48E", tier="premium"),
    area("hpl_exterior", "HPL exterior cladding 6 mm", "Cladding panels", "area", 320, [250, 450], 120, [100, 160], 10,
         {"mode": "tint", "texture": "wood-siding.jpg", "tile_ft": 8, "strength": 0.6}, ["wall", "balcony", "pillar", "roof_edge"], "20+ years",
         "Wash occasionally.", ["UV-stable decors incl. realistic woods", "Very impact resistant"], ["Premium price", "Needs ventilated sub-frame"],
         ["6 mm compact laminate, UV coated"], palette="hpl", default_color="#9A6236", tier="luxury"),
    area("wpc_louvers", "WPC exterior louvers", "Cladding panels", "area", 200, [99, 300], 80, [60, 110], 10,
         {"mode": "tint", "texture": "wood-siding.jpg", "tile_ft": 6, "strength": 0.9}, ["wall", "pillar", "balcony", "gate", "roof_edge"], "15+ years",
         "Wash with mild soap; no polishing.", ["Warm wooden look", "Termite and water resistant"], ["Can fade in harsh sun"],
         ["Co-extruded WPC profiles on aluminium battens"], palette="wpc", default_color="#9A6236"),
    area("fibre_cement", "Fibre-cement siding planks", "Cladding panels", "area", 110, [90, 150], 70, [55, 90], 10,
         {"mode": "tint", "texture": "wood-siding.jpg", "tile_ft": 6, "strength": 0.35}, ["wall", "parapet", "balcony"], "25+ years",
         "Repaint every 8-10 years.", ["Fire resistant, termite proof", "Paintable"], ["Needs painting", "Heavier than WPC"],
         ["8 mm planks, pre-primed"], palette="exterior", default_color="#B9A995"),
    # --- Railings (installed, ex-GST, per running foot) ------------------------------------------------
    area("rail_glass_frameless", "Frameless glass railing (U-channel, 12 mm)", "Railings", "railing", 1950, [1550, 2450], 350, [300, 450], 3,
         {"mode": "glass"}, ["railing"], "20+ years", "Clean glass monthly; check channel sealant yearly.",
         ["Unobstructed view", "Most premium look"], ["Highest cost", "Shows water spots"], ["12 mm toughened glass, aluminium U-channel", "3.5 ft high"],
         rate_unit="rft", labour_unit="rft", tier="luxury"),
    area("rail_ss_glass", "SS 304 posts + 12 mm toughened glass", "Railings", "railing", 1000, [750, 1300], 250, [180, 320], 3,
         {"mode": "glass", "posts": True}, ["railing"], "20+ years", "Clean glass; tighten clamps yearly.",
         ["Glass look at lower cost", "SS 304 won't rust"], ["Posts interrupt the view"], ["SS 304 posts every 4 ft + top rail"],
         rate_unit="rft", labour_unit="rft", tier="premium"),
    area("rail_ss_pipe", "SS 304 pipe railing", "Railings", "railing", 780, [570, 1000], 170, [130, 220], 3,
         {"mode": "rail", "color": "#C9CDD0"}, ["railing"], "20+ years", "Wipe occasionally.",
         ["Rust-free", "Low maintenance"], ["Can look industrial"], ["SS 304, 50 mm top rail, 4 in balusters"], rate_unit="rft", labour_unit="rft"),
    area("rail_ms", "MS railing (powder coated)", "Railings", "railing", 560, [400, 1050], 140, [100, 250], 5,
         {"mode": "rail", "color": "#2C2E30"}, ["railing"], "8-12 years", "Touch up coating and rust spots every 2-3 years.",
         ["Economical", "Any design can be fabricated"], ["Rusts if the coating is damaged"], ["MS hollow sections, powder coated"],
         rate_unit="rft", labour_unit="rft", tier="economy", palette="metal", default_color="#2C2E30"),
    # --- Metal finishes --------------------------------------------------------------------------------
    {**paint("metal_enamel", "Synthetic enamel", "(gates, grills)", "standard", 320, [280, 380], 120, 12, [10, 16], None,
             ["Cheapest way to refresh metalwork", "Rust protection with red-oxide primer"], ["Repaint every 3-5 years"],
             "Sand and repaint rusted spots promptly.", durability="3-5 years"),
     "name": "Synthetic enamel paint (gates & grills)", "brand": None, "category": "Metal finishes", "palette": "metal",
     "default_color": "#2F3A3F", "suitable_for": ["gate", "railing"], "pack_sizes_l": [4, 1], "primer_rate": 200, "primer_coverage_sqft_per_l": 120,
     "render": {"mode": "tint", "texture": "plaster-fine.jpg", "tile_ft": 6, "strength": 0.05},
     "specs": ["1 coat red-oxide primer + 2 coats enamel", "~120 sqft/L per coat"]},
]

site_items = [
    {"id": "scaffolding", "name": "Scaffolding / staging (MS, ~1 month)", "basis": "house_sqft", "rate": 18, "rate_range": [12, 24], "unit": "sqft",
     "default": True, "note": "On all house surfaces (not compound walls). Bamboo staging is cheaper (~₹7-9/sqft) but less safe."},
    {"id": "surface_prep", "name": "Surface preparation (wash, scrape, crack filling)", "basis": "coated_sqft", "rate": 5, "rate_range": [3, 8], "unit": "sqft",
     "default": True, "note": "Painted and textured surfaces. Major cracks or dampness need separate repair."},
    {"id": "waterproof_basecoat", "name": "Waterproof base coat under paint", "basis": "basecoat_sqft", "rate": 14, "rate_range": [10, 20], "unit": "sqft",
     "default": False, "note": "Recommended for walls exposed to driving rain or with past dampness."},
    {"id": "removal", "name": "Removal of existing finish", "basis": "removal_sqft", "rate": 22, "rate_range": [15, 30], "unit": "sqft",
     "default": True, "note": "Only for surfaces marked 'remove existing finish'."},
    {"id": "debris", "name": "Debris removal & site cleaning", "basis": "percent", "rate": 1.5, "rate_range": [1, 3], "unit": "% of works",
     "default": True, "note": "Percentage of material + labour."},
]

cities = [
    {"id": "ahmedabad", "name": "Ahmedabad", "labour_index": 1.0, "material_index": 1.0},
    {"id": "surat", "name": "Surat", "labour_index": 0.98, "material_index": 1.0},
    {"id": "vadodara", "name": "Vadodara", "labour_index": 0.96, "material_index": 1.0},
    {"id": "mumbai", "name": "Mumbai", "labour_index": 1.3, "material_index": 1.05},
    {"id": "pune", "name": "Pune", "labour_index": 1.12, "material_index": 1.02},
    {"id": "bengaluru", "name": "Bengaluru", "labour_index": 1.15, "material_index": 1.03},
    {"id": "hyderabad", "name": "Hyderabad", "labour_index": 1.08, "material_index": 1.02},
    {"id": "chennai", "name": "Chennai", "labour_index": 1.08, "material_index": 1.03},
    {"id": "delhi_ncr", "name": "Delhi NCR", "labour_index": 1.15, "material_index": 1.02},
    {"id": "kolkata", "name": "Kolkata", "labour_index": 0.97, "material_index": 1.02},
    {"id": "jaipur", "name": "Jaipur", "labour_index": 0.95, "material_index": 0.97},
    {"id": "kochi", "name": "Kochi", "labour_index": 1.12, "material_index": 1.04},
]

# Life-cycle data for the long-term cost comparison: (renewal interval in years, renewal cost as a share of the
# installed cost, annual upkeep as a share of the installed cost). Renewal = repaint, reseal or touch-up as the
# maintenance notes describe; materials that outlast the comparison period have no renewal.
LIFECYCLE = {
    "ap_ace": (4.5, 1.0, 0.005), "ap_apex": (6, 1.0, 0.005), "ap_apex_ultima": (7.5, 1.0, 0.005),
    "ap_ultima_protek": (11, 1.0, 0.005), "berger_weathercoat_ll": (7, 1.0, 0.005), "nerolac_excel_total": (7, 1.0, 0.005),
    "dulux_weathershield_max": (8, 1.0, 0.005), "texture_roller": (8, 0.4, 0.005), "stone_spray": (11, 0.5, 0.005),
    "microcement": (2.5, 0.12, 0.005), "stone_jaisalmer": (3.5, 0.06, 0.003), "stone_dholpur": (3.5, 0.06, 0.003),
    "stone_kota": (None, 0, 0.003), "stone_slate": (None, 0, 0.004), "stone_ledge": (None, 0, 0.003),
    "granite_cladding": (None, 0, 0.002), "gvt_300x600": (8, 0.04, 0.003), "gvt_600x1200": (8, 0.04, 0.003),
    "tile_wood_finish": (None, 0, 0.003), "brick_tiles": (4, 0.05, 0.003), "acp_pvdf": (8, 0.05, 0.01),
    "acp_fr": (8, 0.05, 0.01), "hpl_exterior": (None, 0, 0.005), "wpc_louvers": (None, 0, 0.006),
    "fibre_cement": (9, 0.3, 0.004), "rail_glass_frameless": (None, 0, 0.02), "rail_ss_glass": (None, 0, 0.015),
    "rail_ss_pipe": (None, 0, 0.005), "rail_ms": (2.5, 0.15, 0.005), "metal_enamel": (4, 1.0, 0.005),
}
for m in materials:
    years, share, upkeep = LIFECYCLE[m["id"]]
    m.update(renew_years=years, renew_share=share, upkeep_pct=upkeep * 100)

catalog = {
    "currency": "INR",
    "region": "Ahmedabad, Gujarat (base)",
    "rates_updated": "2026-11",
    "rates_note": (
        "Indicative 2026 rates excluding GST: typical dealer prices derived from published MRPs and market listings, "
        "and Ahmedabad labour rates. Each rate has a low-high range. Brand names identify product classes for planning; "
        "always confirm prices, coverage and warranty terms with the dealer and the manufacturer's data sheet."
    ),
    "cities": cities,
    "site_items": site_items,
    "palettes": palettes,
    "materials": materials,
}
OUT.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(materials), "materials;", len(palettes["exterior"]), "exterior shades;", len(site_items), "site items")
