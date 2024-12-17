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

def decode_hitsound(value):
    # Convert an integer hitsound value into a set of hitsound flags.
    # 2 = whistle, 4 = finish, 8 = clap
    # value might be 0,2,4,8,10,12,14 etc.
    s = set()
    val = int(value)
    if val & 2:
        s.add("whistle")
    if val & 4:
        s.add("finish")
    if val & 8:
        s.add("clap")
    return s

def encode_hitsound(hitsound_set):
    # Encode a set of hitsounds back into an integer.
    # Always add 16 (Normal) for slider edges as observed in official osu! files.
    base = 16
    if "whistle" in hitsound_set:
        base += 2
    if "finish" in hitsound_set:
        base += 4
    if "clap" in hitsound_set:
        base += 8
    return base

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
    first_object = True

    for hit_object_xml in root.findall(".//hit-object"):
        hit_object_type = hit_object_xml.attrib.get("type")
        offset = hit_object_xml.attrib.get("offset")
        x = hit_object_xml.attrib.get("x")
        y = hit_object_xml.attrib.get("y")
        new_combo = hit_object_xml.attrib.get("newCombo", "false") == "true"
        main_hitsound_val = hit_object_xml.attrib.get("hitsound", "0")

        if hit_object_type == "1":  # Circle
            object_type = 1 if first_object or not new_combo else 5
            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "hitsound": main_hitsound_val
            })

        elif hit_object_type == "2":  # Slider
            object_type = 2 if first_object or not new_combo else 6
            points = [(x, y)]
            points += [(p.attrib["x"], p.attrib["y"]) for p in hit_object_xml.findall(".//point")]
            curve_type = hit_object_xml.attrib.get("curve", "L")
            backtracks = int(hit_object_xml.attrib.get("backtracks", "0")) + 1
            length = hit_object_xml.attrib.get("length")

            endsounds_attr = hit_object_xml.attrib.get("endsounds", "")
            endsounds_list = endsounds_attr.split("|") if endsounds_attr else []
            # Number of slider edges = backtracks+1 means number of reverses + head. But we must include tail:
            # Actually, a slider with 0 backtracks has 2 edges (head and tail).
            # A slider with n backtracks has n+2 edges.
            # So the total edges = backtracks + 1 (from code) is actually correct? The code previously assumed that.
            # Correction: total edges = backtracks + 1 was old logic. Actually:
            # If backtracks=1, that means 1 repeat, so total edges = 3 (head, reverse, tail).
            # So total_edges = backtracks + 1 is incorrect. It should be backtracks+2.
            total_edges = backtracks + 1  # The original code uses (backtracks+1) tries to represent repeats+head?
            # Let's check official osu logic: For a slider with backtracks=0, endsounds like 8|8 means 2 edges: head and tail.
            # That means total_edges = backtracks+2. Let's use that.
            total_edges = backtracks + 2

            # Parse hitsounds from hit-sound tags:
            hitsound_tags = hit_object_xml.findall("hit-sound")
            hitsound_values = [hs.text for hs in hitsound_tags]

            # Ensure endsounds_list and hitsound_values match total_edges in length:
            # If they are shorter, pad with '0' (no hitsound).
            while len(endsounds_list) < total_edges:
                endsounds_list.append("0")
            while len(hitsound_values) < total_edges:
                hitsound_values.append("0")

            # Decode main hitsound
            main_hitsound_set = decode_hitsound(main_hitsound_val)

            edge_hitsounds = []
            for i in range(total_edges):
                end_val = int(endsounds_list[i]) if endsounds_list[i].isdigit() else 0
                hs_val = int(hitsound_values[i]) if hitsound_values[i].isdigit() else 0

                end_set = decode_hitsound(end_val)
                hs_set = decode_hitsound(hs_val)

                # Union all sets: normal(16) is implicit, so we just combine sets:
                # Also add the main_hitsound_set if needed. The question: Should main hitsound apply to all edges?
                # By looking at examples, main hitsound =0 often. If main_hitsound is not zero, let's union it too:
                combined = main_hitsound_set.union(end_set).union(hs_set)

                # Encode back with normal (16)
                final_val = encode_hitsound(combined)
                edge_hitsounds.append(str(final_val))

            # Join edge hitsounds with |
            edge_hitsound_str = "|".join(edge_hitsounds)

            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "curve_type": map_curve_type(curve_type),
                "points": points,
                "length": length,
                "backtracks": backtracks,
                "hitsound": edge_hitsound_str
            })

        elif hit_object_type == "4":  # Spinner
            object_type = 12
            end_offset = hit_object_xml.attrib.get("endOffset")
            hit_objects.append({
                "type": object_type,
                "x": x,
                "y": y,
                "offset": offset,
                "end_offset": end_offset,
                "hitsound": main_hitsound_val
            })

        elif hit_object_type == "8":  # Hold note
            object_type = 128
            end_offset = hit_object_xml.attrib.get("endOffset")
            # For hold notes, typically center them:
            hit_objects.append({
                "type": object_type,
                "x": "256",
                "y": "192",
                "offset": offset,
                "end_offset": end_offset,
                "hitsound": main_hitsound_val
            })

        first_object = False

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
            f.write(f"{event}\n")
        f.write("//Break Periods\n")
        for b in data['break_periods']:
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
        for timing in timing_points:
            inherited = timing.get('inherited', 'true')
            offset = timing['offset']
            slider_multiplier = float(timing.get('slider_multiplier', 1.0))  # Slider multiplier for inherited points
            sample_set = timing.get('sampleSet', '1')  # Get the sample set
            volume = timing.get('volume', '100')
            special = 1 if timing.get('special', 'false') == 'true' else 0

            if inherited == 'false':  # Non-inherited timing point, use its BPM
                current_bpm = float(timing.get('bpm', 128))
                ms_per_beat = 60000 / current_bpm  # Convert BPM to ms/beat
                f.write(f"{offset},{ms_per_beat},1,1,{sample_set},{volume},1,{special}\n")
            else:  # Inherited timing point (slider velocity control)
                # Adjust second column based on sliderMultiplier
                if slider_multiplier != 1.0:
                    ms_per_beat = -100 / slider_multiplier
                else:
                    ms_per_beat = -100  # Default value if no change in slider multiplier
                f.write(f"{offset},{ms_per_beat},1,1,{sample_set},{volume},0,{special}\n")  # Third column is always '1'
        
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
                f.write(f"{x},{y},{offset},128,{hit_object['hitsound']},{hit_object['end_offset']},0:0:0:0\n")

def main():
    input_file = "Drop - Granat (TheHowl) [Pro].hbxml"
    output_file = "Drop - Granat (TheHowl) [Pro].osu"

    # Parse the XML file
    data = parse_xml(input_file)
    
    # Convert to osu! file
    convert_to_osu(data, output_file)

if __name__ == "__main__":
    main()