import xml.etree.ElementTree as ET

# Function to map the game's curve type to osu! curve types
def map_curve_type(curve_type):
    if curve_type == "p":  # Perfect (circular)
        return "P"
    elif curve_type == "l":  # Linear
        return "L"
    elif curve_type == "b":  # Bezier
        return "B"
    elif curve_type == "c":  # Catmull
        return "C"
    else:
        return "L"  # Default to linear if undefined or unknown

def parse_xml(file_path):
    # Load and parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Extract meta information
    meta = root.find("meta")
    title = meta.attrib.get("title", "Unknown")
    artist = meta.attrib.get("artist", "Unknown")
    version = meta.attrib.get("version", "Unknown")
    creator = meta.attrib.get("creator", "Unknown")
    source = meta.attrib.get("source", "")
    tags = meta.attrib.get("tags", "")

    # Extract general info
    general = root.find("general")
    audio_filename = general.attrib.get("audioFilename", "audio.mp3")
    audio_leadin = general.attrib.get("audioLeadIn", "0")  # Saving Audio LeadIn time
    preview_time = general.attrib.get("previewOffset", "-1")
    letterbox_in_breaks = general.attrib.get("letterboxDuringBreaks", "false")

    # Extract difficulty info
    difficulty = root.find("difficulty")
    hp_drain = difficulty.attrib.get("hpDrainRate", "5")
    circle_size = difficulty.attrib.get("circleSize", "5")
    overall_difficulty = difficulty.attrib.get("overallDifficulty", "5")
    approach_rate = difficulty.attrib.get("approachRate", "5")
    slider_multiplier = difficulty.attrib.get("sliderMultiplier", "1")
    slider_tick_rate = difficulty.attrib.get("sliderTickRate", "1")

    # Extract timing points
    timing_points = []
    for timing in root.findall(".//timing-point"):
        timing_points.append({
            "offset": timing.attrib.get("offset"),
            "bpm": timing.attrib.get("bpm"),
            "slider_multiplier": timing.attrib.get("sliderMultiplier", "1"),
            "inherited": timing.attrib.get("inherited", "true"),
            "volume": timing.attrib.get("volume", "100"),  # Extract volume
            "special": timing.attrib.get("special", "false"),  # Extract special flag
        })

    # Extract hit objects
    hit_objects = []
    first_object = True  # This will track whether we're processing the first object

    for hit_object_xml in root.findall(".//hit-object"):
        hit_object_type = hit_object_xml.attrib.get("type")
        offset = hit_object_xml.attrib.get("offset")
        x = hit_object_xml.attrib.get("x")
        y = hit_object_xml.attrib.get("y")
        new_combo = hit_object_xml.attrib.get("newCombo", "false") == "true"

        # Handle different hit object types
        if hit_object_type == "1":  # Circle
            object_type = 1 if first_object or not new_combo else 5  # Add 4 if newCombo and not first object
            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "hitsound": hit_object_xml.attrib.get("hitsound", "0")
            })
        elif hit_object_type == "2":  # Slider
            object_type = 2 if first_object or not new_combo else 6  # Add 4 if newCombo and not first object
            points = [(hit_object_xml.attrib["x"], hit_object_xml.attrib["y"])]  # Start point
            points += [(p.attrib["x"], p.attrib["y"]) for p in hit_object_xml.findall(".//point")]  # Add curve points
            curve_type = hit_object_xml.attrib.get("curve", "L")  # Get curve type
            backtracks = int(hit_object_xml.attrib.get("backtracks", "0")) + 1  # Add 1 to backtracks for osu!
            length = hit_object_xml.attrib.get("length")

            # Main hitsound
            main_hitsound = hit_object_xml.attrib.get("hitsound", "0")

            # Parse hitsounds for individual parts of the slider
            hit_sounds = [main_hitsound] * (backtracks + 1)  # Start + backtracks + end
            individual_hit_sounds = [int(hs.text) for hs in hit_object_xml.findall("hit-sound")]

            # Ensure length of hitsounds matches slider parts
            for i in range(len(hit_sounds)):
                if i < len(individual_hit_sounds):
                    additional_hitsound = individual_hit_sounds[i]
                    if additional_hitsound != int(main_hitsound) and additional_hitsound != 0:
                        hit_sounds[i] = str(int(hit_sounds[i]) + additional_hitsound)

            # Now process the endsounds (if any)
            endsounds = hit_object_xml.attrib.get("endsounds", "").split("|")
            if endsounds and endsounds[0]:
                for i in range(len(endsounds)):
                    if i < len(hit_sounds):
                        additional_endsound = int(endsounds[i])
                        if additional_endsound != int(main_hitsound) and additional_endsound != 0:
                            hit_sounds[-(i + 1)] = str(int(hit_sounds[-(i + 1)]) + additional_endsound)

            hit_sounds = "|".join(hit_sounds)

            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "curve_type": map_curve_type(curve_type),
                "points": points,
                "length": length,
                "backtracks": backtracks,
                "hitsound": hit_sounds
            })
        elif hit_object_type == "4":  # Spinner
            object_type = 12  # Spinners are always 12 in osu!
            end_offset = hit_object_xml.attrib.get("endOffset")
            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "end_offset": end_offset,
                "hitsound": hit_object_xml.attrib.get("hitsound", "0")
            })
        elif hit_object_type == "8":  # Hold note (treated as slider for now)
            object_type = 128  # For hold notes
            end_offset = hit_object_xml.attrib.get("endOffset")
            hit_objects.append({
                "type": object_type,
                "x": "256",  # Center of osu! screen
                "y": "192",  # Center of osu! screen
                "offset": offset,
                "end_offset": end_offset,
                "hitsound": hit_object_xml.attrib.get("hitsound", "0")
            })

        first_object = False  # After the first hit object

    # Extract colors
    colors = []
    for color in root.findall(".//combo"):
        r = color.attrib.get("red")
        g = color.attrib.get("green")
        b = color.attrib.get("blue")
        colors.append((r, g, b))

    # Extract events (backgrounds and breaks)
    background_events = []
    break_periods = []
    backgrounds = root.findall(".//background")
    breaks = root.findall(".//break")

    for background in backgrounds:
        filename = background.attrib.get("filename", "")
        background_events.append(f"0,0,\"{filename}\",0,0")

    for brk in breaks:
        start = brk.attrib.get("offset")
        end = brk.attrib.get("endOffset")
        break_periods.append(f"2,{start},{end}")

    return {
        "title": title,
        "artist": artist,
        "version": version,
        "creator": creator,
        "source": source,
        "tags": tags,
        "audio_filename": audio_filename,
        "audio_leadin": audio_leadin,
        "preview_time": preview_time,
        "letterbox_in_breaks": letterbox_in_breaks,
        "hp_drain": hp_drain,
        "circle_size": circle_size,
        "overall_difficulty": overall_difficulty,
        "approach_rate": approach_rate,
        "slider_multiplier": slider_multiplier,
        "slider_tick_rate": slider_tick_rate,
        "timing_points": timing_points,
        "hit_objects": hit_objects,
        "colors": colors,
        "background_events": background_events,
        "break_periods": break_periods
    }

def convert_to_osu(data, output_file):
    timing_points = data['timing_points']
    hit_objects = data['hit_objects']
    
    with open(output_file, 'w') as f:
        # Write [General] section
        f.write("osu file format v14\n\n")
        f.write("[General]\n")
        f.write(f"AudioFilename: {data['audio_filename']}\n")
        f.write(f"AudioLeadIn: {data['audio_leadin']}\n")
        f.write(f"PreviewTime: {data['preview_time']}\n")
        f.write("Countdown: 0\n")
        f.write("SampleSet: Normal\n")
        f.write("StackLeniency: 0.7\n")
        f.write("Mode: 0\n")
        f.write("LetterboxInBreaks: 0\n")
        f.write("WidescreenStoryboard: 1\n\n")
        
        # Write [Editor] section
        f.write("[Editor]\n")
        f.write("DistanceSpacing: 1\n")
        f.write("BeatDivisor: 2\n")
        f.write("GridSize: 8\n")
        f.write("TimelineZoom: 1\n\n")
        
        # Write [Metadata] section
        f.write("[Metadata]\n")
        f.write(f"Title:{data['title']}\n")
        f.write(f"TitleUnicode:{data['title']}\n")
        f.write(f"Artist:{data['artist']}\n")
        f.write(f"ArtistUnicode:{data['artist']}\n")
        f.write(f"Creator:{data['creator']}\n")
        f.write(f"Version:{data['version']}\n")
        f.write(f"Source:{data['source']}\n")
        f.write(f"Tags:{data['tags']}\n")
        f.write("BeatmapID:0\n")
        f.write("BeatmapSetID:-1\n\n")
        
        # Write [Difficulty] section
        f.write("[Difficulty]\n")
        f.write(f"HPDrainRate:{data['hp_drain']}\n")
        f.write(f"CircleSize:{data['circle_size']}\n")
        f.write(f"OverallDifficulty:{data['overall_difficulty']}\n")
        f.write(f"ApproachRate:{data['approach_rate']}\n")
        f.write(f"SliderMultiplier:{data['slider_multiplier']}\n")
        f.write(f"SliderTickRate:{data['slider_tick_rate']}\n\n")
        
        # Write [Events] section
        f.write("[Events]\n")
        f.write("//Background and Video events\n")
        for event in data['background_events']:
            f.write(f"{event}\n")  # Write each background event
        f.write("//Break Periods\n")
        for b in data['break_periods']:  # Changed from 'breaks' to 'break_periods'
            f.write(f"{b}\n")
        f.write("//Storyboard Layer 0 (Background)\n")
        f.write("//Storyboard Layer 1 (Fail)\n")
        f.write("//Storyboard Layer 2 (Pass)\n")
        f.write("//Storyboard Layer 3 (Foreground)\n")
        f.write("//Storyboard Sound Samples\n")
        f.write("//Background Colour Transformations\n")
        f.write("3,100,163,162,255\n\n")
        
        # Write [TimingPoints] section
        f.write("[TimingPoints]\n")
        current_bpm = None
        for timing in timing_points:
            inherited = timing.get('inherited', 'true')
            offset = timing['offset']
            if inherited == 'false':  # Non-inherited timing point, use its BPM
                current_bpm = float(timing.get('bpm', 128))
                ms_per_beat = 60000 / current_bpm  # Convert BPM to ms/beat
                special = 1 if timing.get('special', 'false') == 'true' else 0
                f.write(f"{offset},{ms_per_beat},{timing.get('slider_multiplier', 1)},1,0,{timing.get('volume', 100)},1,{special}\n")
            else:  # Inherited timing point
                special = 1 if timing.get('special', 'false') == 'true' else 0
                f.write(f"{offset},-100,{timing.get('slider_multiplier', 1)},1,0,{timing.get('volume', 100)},0,{special}\n")
        
        # Write [Colours] section
        f.write("\n[Colours]\n")
        for i, color in enumerate(data['colors']):
            f.write(f"Combo{i+1} : {color[0]},{color[1]},{color[2]}\n")
        
        # Write [HitObjects] section
        f.write("\n[HitObjects]\n")
        for hit_object in hit_objects:
            x, y, offset, obj_type = hit_object['x'], hit_object['y'], hit_object['offset'], hit_object['type']
            if obj_type in {1, 5}:  # Circle
                f.write(f"{x},{y},{offset},{obj_type},{hit_object['hitsound']},0:0:0:0:\n")
            elif obj_type in {2, 6}:  # Slider
                points = "|".join([f"{p[0]}:{p[1]}" for p in hit_object['points']])
                f.write(f"{x},{y},{offset},{obj_type},0,{hit_object['curve_type']}|{points},{hit_object['backtracks']},{hit_object['length']},{hit_object['hitsound']},0:0|0:0|0:0,0:0:0:0:\n")
            elif obj_type == 12:  # Spinner
                f.write(f"{x},{y},{offset},12,{hit_object['hitsound']},{hit_object['end_offset']},0:0:0:0:\n")
            elif obj_type == 128:  # Hold
                f.write(f"{x},{y},{offset},128,{hit_object['hitsound']},{hit_object['end_offset']},0:0:0:0:\n")

def main():
    input_file = "M2U - Masquerade (TheHowl) [Novice].hbxml"
    output_file = "M2U - Masquerade (TheHowl) [Novice].osu"

    # Parse the XML file
    data = parse_xml(input_file)
    
    # Convert to osu! file
    convert_to_osu(data, output_file)

if __name__ == "__main__":
    main()