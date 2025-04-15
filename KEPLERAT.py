import dearpygui.dearpygui as dpg
import os, json, platform, subprocess, math

# Глобальное состояние для хранения загруженных файлов и промежуточных данных.
state = {
    "kepplerate_file": None,
    "landing_file": None,
    "docking_points": {"left": None, "right": None},  # будут хранить выбранные атомы
    "atom_groups": None,     # Группировка: {group_key: [atom_id, ...]}
    "atoms": None,           # Список атомов из landing molecule
    "bonds": None,           # Список связей: [(id1, id2), ...]
    "canvas_coords": {}      # Соответствие: {atom_id: (cx, cy)}
}

# Глобальные множества для выбранных групп для левой и правой docking point
selected_left_groups = set()
selected_right_groups = set()

# Глобальный флаг для режима выбора docking point:
current_docking_mode = None  # Может быть "left", "right" или None

# Глобальная переменная для логирования.
log_messages = ""

def log_message(msg):
    global log_messages
    log_messages += msg + "\n"
    dpg.set_value("log_text", log_messages)
    print(msg)

def open_system_file_dialog(filetypes, initial_dir=None):
    """
    На macOS использует osascript для вызова нативного диалога выбора файла,
    на других платформах — Tkinter.
    """
    if platform.system() == "Darwin":
        prompt = "Select a file"
        if filetypes and len(filetypes) > 0 and filetypes[0][1].startswith("*."):
            ext = filetypes[0][1][2:]
            script = f'POSIX path of (choose file with prompt "{prompt}" of type {{"{ext}"}})'
        else:
            script = f'POSIX path of (choose file with prompt "{prompt}")'
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return ""
        except Exception as e:
            print("Error invoking osascript:", e)
            return ""
    else:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            if initial_dir is None:
                initial_dir = os.path.expanduser("~")
            file_path = filedialog.askopenfilename(initialdir=initial_dir, filetypes=filetypes)
            root.destroy()
            return file_path
        except Exception as e:
            print("Error with tkinter file dialog:", e)
            return ""

def open_kepplerate_file():
    file_path = open_system_file_dialog(
        filetypes=[("MOL Files", "*.mol"), ("All Files", "*.*")]
    )
    if file_path:
        if file_path.lower().endswith(".mol"):
            state["kepplerate_file"] = file_path
            log_message(f"Kepplerate file loaded: {file_path}")
        else:
            log_message("Error: Kepplerate file format incorrect. Only .mol files allowed.")

def open_landing_file():
    file_path = open_system_file_dialog(
        filetypes=[("MOL Files", "*.mol"), ("All Files", "*.*")]
    )
    if file_path:
        if file_path.lower().endswith(".mol"):
            state["landing_file"] = file_path
            log_message(f"Landing molecule file loaded: {file_path}")
        else:
            log_message("Error: Landing molecule file format incorrect. Only .mol files allowed.")

def parse_mol_file(file_path):
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        log_message(f"Error opening MOL file {file_path}: {e}")
        return [], []
    if len(lines) < 4:
        log_message("Error: MOL file format incorrect (not enough lines).")
        return [], []
    try:
        num_atoms = int(lines[3][:3].strip())
        num_bonds = int(lines[3][3:6].strip())
    except Exception as e:
        log_message(f"Error parsing header counts: {e}")
        return [], []
    atoms = []
    for i in range(4, 4 + num_atoms):
        line = lines[i]
        try:
            x = float(line[0:10].strip())
            y = float(line[10:20].strip())
            z = float(line[20:30].strip())
            atom_symbol = line[31:34].strip()
            atoms.append({"id": i - 4, "symbol": atom_symbol, "x": x, "y": y, "z": z, "bond_count": 0})
        except Exception as e:
            log_message(f"Error parsing line {i+1} in MOL file: {e}")
    bonds = []
    start_bond = 4 + num_atoms
    for j in range(start_bond, start_bond + num_bonds):
        try:
            line = lines[j]
            idx1 = int(line[0:3].strip()) - 1
            idx2 = int(line[3:6].strip()) - 1
            bonds.append((idx1, idx2))
            atoms[idx1]["bond_count"] += 1
            atoms[idx2]["bond_count"] += 1
        except Exception as e:
            log_message(f"Error parsing bond line {j+1}: {e}")
    return atoms, bonds

def draw_landing_molecule(atoms, bonds):
    dpg.delete_item("landing_drawlist", children_only=True)
    state["canvas_coords"] = {}
    xs = [atom["x"] for atom in atoms]
    ys = [atom["y"] for atom in atoms]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    canvas_width = 400
    canvas_height = 400
    pad = 20
    scale_x = (canvas_width - 2 * pad) / (max_x - min_x) if max_x != min_x else 1
    scale_y = (canvas_height - 2 * pad) / (max_y - min_y) if max_y != min_y else 1
    for atom in atoms:
        cx = pad + (atom["x"] - min_x) * scale_x
        cy = pad + (atom["y"] - min_y) * scale_y
        state["canvas_coords"][atom["id"]] = (cx, cy)
        color_map = {
            "N": [0, 0, 255, 255],
            "C": [128, 128, 128, 255],
            "O": [255, 0, 0, 255],
            "H": [255, 255, 255, 255],
            "Mo": [0, 128, 255, 255],
            "Fe": [255, 165, 0, 255]
        }
        col = color_map.get(atom["symbol"], [0, 0, 0, 255])
        dpg.draw_circle((cx, cy), 5, color=col, fill=col, parent="landing_drawlist")
        dpg.draw_text((cx + 7, cy), atom["symbol"], color=[0, 0, 0, 255], parent="landing_drawlist")
    for bond in bonds:
        id1, id2 = bond
        if id1 in state["canvas_coords"] and id2 in state["canvas_coords"]:
            dpg.draw_line(state["canvas_coords"][id1], state["canvas_coords"][id2],
                          color=[0, 0, 0, 255], thickness=2, parent="landing_drawlist")

def drawlist_click_callback(sender, app_data):
    global current_docking_mode
    if current_docking_mode is None:
        return
    mouse_pos = dpg.get_drawing_mouse_pos()
    min_dist = float('inf')
    selected_atom = None
    for atom_id, (cx, cy) in state["canvas_coords"].items():
        dist = math.hypot(mouse_pos[0] - cx, mouse_pos[1] - cy)
        if dist < min_dist:
            min_dist = dist
            selected_atom = atom_id
    threshold = 10  # пикселей
    if selected_atom is not None and min_dist < threshold:
        if current_docking_mode == "left":
            state["docking_points"]["left"] = next((atom for atom in state["atoms"] if atom["id"] == selected_atom), None)
            log_message(f"Left docking point selected: Atom id {selected_atom}")
        elif current_docking_mode == "right":
            state["docking_points"]["right"] = next((atom for atom in state["atoms"] if atom["id"] == selected_atom), None)
            log_message(f"Right docking point selected: Atom id {selected_atom}")
        update_docking_points_display()
    else:
        log_message("No atom close enough to selection point.")
    current_docking_mode = None

def update_docking_points_display():
    left = state["docking_points"].get("left")
    right = state["docking_points"].get("right")
    text = ""
    if left:
        text += f"Left docking point: {left['symbol']} (x={left['x']:.2f})\n"
    if right:
        text += f"Right docking point: {right['symbol']} (x={right['x']:.2f})\n"
    dpg.set_value("docking_points_text", text)

def set_left_docking_mode(sender, app_data):
    global current_docking_mode
    current_docking_mode = "left"
    log_message("Click on the schematic to select LEFT docking point.")

def set_right_docking_mode(sender, app_data):
    global current_docking_mode
    current_docking_mode = "right"
    log_message("Click on the schematic to select RIGHT docking point.")

def update_group_selection_panels(groups):
    if dpg.does_item_exist("left_groups_container"):
        dpg.delete_item("left_groups_container", children_only=True)
    if dpg.does_item_exist("right_groups_container"):
        dpg.delete_item("right_groups_container", children_only=True)
    for group_key in groups.keys():
        left_tag = f"left_checkbox_{group_key}"
        right_tag = f"right_checkbox_{group_key}"
        dpg.add_checkbox(label=group_key, tag=left_tag, parent="left_groups_container",
                         callback=lambda s, a, u=group_key: left_checkbox_callback(s, a, u))
        dpg.add_checkbox(label=group_key, tag=right_tag, parent="right_groups_container",
                         callback=lambda s, a, u=group_key: right_checkbox_callback(s, a, u))
    check_export_availability()

def left_checkbox_callback(sender, app_data, group_key):
    if app_data:
        selected_left_groups.add(group_key)
    else:
        selected_left_groups.discard(group_key)
    check_export_availability()

def right_checkbox_callback(sender, app_data, group_key):
    if app_data:
        selected_right_groups.add(group_key)
    else:
        selected_right_groups.discard(group_key)
    check_export_availability()

def check_export_availability():
    if selected_left_groups and selected_right_groups:
        dpg.enable_item("export_button")
    else:
        dpg.disable_item("export_button")

def analyze_landing_molecule_callback(sender, app_data):
    if not state["landing_file"]:
        log_message("Error: No landing molecule file loaded.")
        return
    atoms, bonds = parse_mol_file(state["landing_file"])
    if not atoms:
        log_message("Error: No atoms parsed from landing molecule file.")
        return
    state["atoms"] = atoms
    state["bonds"] = bonds
    left = min(atoms, key=lambda a: a["x"])
    right = max(atoms, key=lambda a: a["x"])
    state["docking_points"] = {"left": left, "right": right}
    groups = {}
    for atom in atoms:
        group_key = f"{atom['symbol']} ({atom['bond_count']} bonds)"
        groups.setdefault(group_key, []).append(atom["id"])
    state["atom_groups"] = groups
    analysis_text = (f"Default docking points:\nLeft: {left['symbol']} (x={left['x']:.2f})\n"
                     f"Right: {right['symbol']} (x={right['x']:.2f})\n"
                     f"Available groups: {list(groups.keys())}")
    dpg.set_value("docking_points_text", analysis_text)
    log_message("Landing molecule analysis completed.")
    update_group_selection_panels(groups)
    draw_landing_molecule(atoms, bonds)

def calculate_callback(sender, app_data):
    log_message("Calculation module initiated. (Integration pending)")
    dpg.set_value("results_text", "Calculation results will be shown here.")

def generate_animation_callback(sender, app_data):
    log_message("Animation generation initiated. (To be launched in a separate window/file)")

def export_json_callback(sender, app_data):
    if not (selected_left_groups and selected_right_groups):
        log_message("Error: Please select at least one group for both left and right docking points.")
        return
    atomgrps = {
        "left": [],
        "right": []
    }
    for grp in selected_left_groups:
        atomgrps["left"].append({"group": grp, "ids": state["atom_groups"].get(grp, []), "joinNbr": 0})
    for grp in selected_right_groups:
        atomgrps["right"].append({"group": grp, "ids": state["atom_groups"].get(grp, []), "joinNbr": 1})
    molfiles = {
        "keplerate_mol": state["kepplerate_file"] if state["kepplerate_file"] else "",
        "ligand1_mol": state["landing_file"] if state["landing_file"] else ""
    }
    affinity_key = ""
    for grp in selected_left_groups:
        left_ids = state["atom_groups"].get(grp, [])
        if left_ids:
            affinity_key = str(left_ids[0])
            break
    calcoptions = {
        "numCycles": 10000,
        "ligAffinity": {affinity_key: ["0", "1"]} if affinity_key else {}
    }
    atomtypes = {
        "types": {
            "0": {
                "ids": list(set().union(*(state["atom_groups"].get(g, []) for g in selected_left_groups))),
                "elem": "LeftGroups",
                "color": "blue",
                "neigh": {"O": 6}
            },
            "1": {
                "ids": list(set().union(*(state["atom_groups"].get(g, []) for g in selected_right_groups))),
                "elem": "RightGroups",
                "color": "green",
                "neigh": {"O": 7}
            },
            "2": {
                "ids": [],
                "elem": "Fe",
                "color": "orange",
                "neigh": {"O": 6}
            }
        },
        "gifpath": "./jlj4508x.gif"
    }
    try:
        with open("atomgrps.json", "w") as f:
            json.dump(atomgrps, f, indent=4)
        with open("molfiles.json", "w") as f:
            json.dump(molfiles, f, indent=4)
        with open("calcoptions.json", "w") as f:
            json.dump(calcoptions, f, indent=4)
        with open("atomtypes.json", "w") as f:
            json.dump(atomtypes, f, indent=4)
        log_message("JSON configuration files exported successfully.")
    except Exception as e:
        log_message(f"Error exporting JSON files: {e}")

# --- Основной блок создания интерфейса ---
dpg.create_context()

with dpg.window(label="Molecule Docking Interface", width=980, height=920):

    with dpg.tab_bar():
        with dpg.tab(label="Molecule Loading"):
            dpg.add_text("Load Kepplerate (.mol) file:")
            dpg.add_button(label="Load Kepplerate", callback=lambda s, a: open_kepplerate_file())
            dpg.add_spacer(height=10)
            dpg.add_text("Load Landing Molecule (.mol) file:")
            dpg.add_button(label="Load Landing Molecule", callback=lambda s, a: open_landing_file())
        
        with dpg.tab(label="Landing Configuration"):
            dpg.add_text("Analyze landing molecule to determine docking points and atom groups.")
            dpg.add_button(label="Analyze Landing Molecule", callback=analyze_landing_molecule_callback)
            dpg.add_separator()
            dpg.add_text("", tag="docking_points_text")
            dpg.add_spacer(height=10)
            dpg.add_text("Schematic view of landing molecule:")
            dpg.add_drawlist(width=400, height=400, tag="landing_drawlist", callback=drawlist_click_callback)
            dpg.add_spacer(height=10)
            dpg.add_button(label="Set Left Docking Point", callback=set_left_docking_mode)
            dpg.add_button(label="Set Right Docking Point", callback=set_right_docking_mode)
            dpg.add_spacer(height=10)
            dpg.add_text("Select groups for Left Docking Point:")
            dpg.add_child_window(tag="left_groups_container", width=300, height=150)
            dpg.add_spacer(height=10)
            dpg.add_text("Select groups for Right Docking Point:")
            dpg.add_child_window(tag="right_groups_container", width=300, height=150)
        
        with dpg.tab(label="Calculation"):
            dpg.add_text("Calculation module (to be integrated later).")
            dpg.add_button(label="Calculate", callback=calculate_callback)
            dpg.add_separator()
            dpg.add_text("Calculation Results:", tag="results_text")
        
        with dpg.tab(label="Animation"):
            dpg.add_text("Generate animation (all configurations in one rotation).")
            dpg.add_button(label="Generate Animation", callback=generate_animation_callback)
        
        with dpg.tab(label="Export Configurations"):
            dpg.add_text("Export JSON configuration files for inter-module communication.")
            dpg.add_button(label="Export JSON Configurations", tag="export_button", callback=export_json_callback)
    
    with dpg.collapsing_header(label="Log", default_open=True):
         dpg.add_child_window(tag="log_child", width=-1, height=150)
         dpg.add_text("", tag="log_text")

dpg.create_viewport(title="Molecule Docking Project", width=980, height=920)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()

