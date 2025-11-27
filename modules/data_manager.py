import json
import os
import shutil
from .constants import Constants

class ItemDatabase:
    """Loads and holds all item data from the /data/items/ directory."""
    def __init__(self): 
        self.items = self._load_items_from_dir(Constants.ITEMS_DIR)
        
    def _load_items_from_dir(self, directory: str):
        choices = {}
        if not os.path.exists(directory): 
            print(f"Warning: Items directory not found: {directory}. Using empty database.")
            return choices
            
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        item_object = json.load(f)
                        name_obj = item_object.get('name')
                        
                        if isinstance(name_obj, dict):
                            # 1. Set the display name to English (default) for internal logic
                            if 'en' in name_obj:
                                item_object['name'] = str(name_obj['en']).strip()
                            
                            # 2. Store the full dictionary for localization support
                            item_object['names'] = name_obj

                            # 3. Index ALL languages so OCR can find them
                            for lang_code, name_val in name_obj.items():
                                if name_val:
                                    choices[str(name_val).strip()] = item_object
                                    
                        elif isinstance(name_obj, str): 
                             item_name = str(name_obj).strip()
                             item_object['name'] = item_name
                             # Ensure 'names' dict exists even for single-string legacy items
                             item_object['names'] = {'en': item_name}
                             choices[item_name] = item_object
                        else:
                            print(f"Warning: Item in {filename} has no usable name. Skipping.")

                except Exception as e:
                    print(f"Error loading item file {filename}: {e}")
        return choices

class DataManager:
    """Handles all game data and user progress, acting as the single source of truth."""
    def __init__(self, items):
        self.items = items
        self.item_names_lower = [name.lower() for name in self.items.keys()]
        self.lower_to_actual_name = {name.lower(): name for name in self.items.keys()}
        
        self.hideout_data = self._load_json_dir(Constants.HIDEOUT_DIR)
        for station in self.hideout_data:
            if isinstance(station.get('name'), dict) and 'en' in station['name']: station['name'] = station['name']['en']

        self.project_data = self._load_json(Constants.PROJECTS_FILE, [])
        for project in self.project_data:
            if isinstance(project.get('name'), dict) and 'en' in project['name']: project['name'] = project['name']['en']
            for phase in project.get('phases', []):
                if isinstance(phase.get('name'), dict) and 'en' in phase['name']: phase['name'] = phase['name']['en']
        
        self.trade_data = self._load_json(Constants.TRADES_FILE, [])
        self.item_to_trades_map = {}
        for trade in self.trade_data:
            item_id = trade.get('itemId')
            if item_id: self.item_to_trades_map.setdefault(item_id, []).append(trade)
            
        self.quest_data = self._load_json_dir(Constants.QUESTS_DIR)
        
        self.user_progress = self._load_json(Constants.PROGRESS_FILE, {})
        
        # --- ID MAPPING ---
        # 1. Build ID -> Item Object Map for fast lookups
        self.id_to_item_map = {}
        for item in self.items.values():
            if item.get('id'):
                self.id_to_item_map[item['id']] = item
        
        # 2. Build ID -> English Name Map (Stable for internal use)
        # We assume item['name'] is already set to English in ItemDatabase._load_items_from_dir
        self.id_to_name_map = {i_id: item.get('name', 'Unknown') for i_id, item in self.id_to_item_map.items()}
        
        # Create initial backup on startup
        self._backup_progress()

    def _load_json(self, filepath: str, default=None):
        if not os.path.exists(filepath): return default or {}
        try: 
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default or {}

    def _load_json_dir(self, directory: str):
        data_list = []
        if not os.path.exists(directory):
             print(f"Warning: Data directory not found: {directory}. Using empty list.")
             return data_list
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data_list.append(json.load(f))
                except Exception as e:
                    print(f"Error loading data file {filename} from {directory}: {e}")
        return data_list

    def _backup_progress(self):
        """Creates a copy of progress.json as progress.json.bak"""
        if os.path.exists(Constants.PROGRESS_FILE):
            try:
                backup_path = Constants.PROGRESS_FILE + ".bak"
                shutil.copy2(Constants.PROGRESS_FILE, backup_path)
                print(f"Backup created at {backup_path}")
            except Exception as e:
                print(f"Failed to create backup: {e}")

    def save_user_progress(self):
        """
        Saves the current user_progress dict to disk safely using Atomic Write.
        """
        try:
            temp_file = Constants.PROGRESS_FILE + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_progress, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, Constants.PROGRESS_FILE)
        except Exception as e:
            print(f"Error saving progress: {e}")
            if os.path.exists(Constants.PROGRESS_FILE + ".tmp"):
                try: os.remove(Constants.PROGRESS_FILE + ".tmp")
                except: pass

    def reload_progress(self): 
        self.user_progress = self._load_json(Constants.PROGRESS_FILE, {})
        self._backup_progress()
        print("Progress file reloaded and backed up.")
    
    # --- NOTE HANDLING ---
    def get_item_note(self, item_id: str) -> str:
        notes = self.user_progress.get('item_notes', {})
        return notes.get(item_id, "")

    def set_item_note(self, item_id: str, note: str):
        if 'item_notes' not in self.user_progress:
            self.user_progress['item_notes'] = {}
        if note and note.strip():
            self.user_progress['item_notes'][item_id] = note.strip()
        else:
            if item_id in self.user_progress['item_notes']:
                del self.user_progress['item_notes'][item_id]
        self.save_user_progress()

    # --- LOCALIZATION HELPER ---
    def get_localized_name(self, item_identifier, lang_code='en'):
        """
        Resolves the name of an item in the requested language.
        item_identifier: Can be an Item Dictionary or an Item ID string.
        """
        item = None
        if isinstance(item_identifier, dict):
            item = item_identifier
        elif isinstance(item_identifier, str):
            item = self.id_to_item_map.get(item_identifier)
            
        if not item:
            # Fallback if ID not found, return the ID formatted nicely
            if isinstance(item_identifier, str):
                return item_identifier.replace('_', ' ').title()
            return "Unknown"

        # Try to find the specific language in the 'names' dict
        names = item.get('names', {})
        if lang_code in names:
            return names[lang_code]
        
        # Fallback to default 'name' field (usually English)
        return item.get('name', 'Unknown')

    # --- EXISTING LOGIC ---
    def get_filtered_quests(self, tracked_only: bool = False):
        if 'quests' not in self.user_progress: self.user_progress['quests'] = {}
        all_quest_info = []
        for quest in self.quest_data:
            q_id = quest.get('id')
            if not q_id: continue
            info = quest.copy()
            if isinstance(info.get('name'), dict) and 'en' in info['name']: info['name'] = info['name']['en']
            original, flat = info.get('objectives', []), []
            for obj in original:
                if isinstance(obj, dict) and 'en' in obj: flat.append(obj['en'])
                elif isinstance(obj, str): flat.append(obj)
            info['objectives'] = flat
            progress = self.user_progress['quests'].get(q_id, {})
            info.update(is_completed=progress.get('quest_completed', False), is_tracked=progress.get('is_tracked', False), objectives_completed=progress.get('objectives_completed', []))
            all_quest_info.append(info)

        custom_order = self.user_progress.get('quest_order', [])
        
        def sort_key(q):
            q_id = q['id']
            order_index = custom_order.index(q_id) if q_id in custom_order else len(custom_order)
            return (not q['is_tracked'], order_index, q['is_completed'])
            
        sorted_quests = sorted(all_quest_info, key=sort_key)

        if tracked_only:
            tracked = [q for q in all_quest_info if q['is_tracked'] and not q['is_completed']]
            return sorted(tracked, key=lambda q: custom_order.index(q['id']) if q['id'] in custom_order else 999)
        else:
            return sorted_quests

    def find_trades_for_item(self, item_name: str):
        item = self.get_item_by_name(item_name)
        return self.item_to_trades_map.get(item['id'], []) if item and 'id' in item else []
    
    def find_hideout_requirements(self, item_name: str):
        results, target_item = [], self.get_item_by_name(item_name)
        if not target_item or 'id' not in target_item: return []
        tid = target_item['id']
        h_inv = self.user_progress.get('hideout_inventory', {})
        for station in self.hideout_data:
            sid, sname, cur_lvl = station.get('id'), station.get('name'), self.user_progress.get(station.get('id'), 0)
            for lvl_info in station.get('levels', []):
                lvl = lvl_info.get('level', 0)
                if lvl <= cur_lvl: continue
                req_type = 'next' if lvl == cur_lvl + 1 else 'future'
                for req in lvl_info.get('requirementItemIds', []):
                    if req.get('itemId') == tid:
                        needed, owned = req.get('quantity', 0), h_inv.get(sid, {}).get(str(lvl), {}).get(req.get('itemId'), 0)
                        if (rem := needed - owned) > 0:
                            results.append((f"{sname} (Lvl {lvl}): x{rem}", req_type))
        return results

    def find_project_requirements(self, item_name: str):
        results, target_item = [], self.get_item_by_name(item_name)
        if not target_item or 'id' not in target_item: return []
        tid = target_item['id']
        p_prog = self.user_progress.get('projects', {})
        for proj in self.project_data:
            pid, pname = proj.get('id'), proj.get('name')
            if 'Project' in pname:
                pname = pname.replace('Project', '').strip()

            prog = p_prog.get(pid, {'completed_phase': 0, 'inventory': {}})
            comp_phase, inv = prog.get('completed_phase', 0), prog.get('inventory', {})
            for phase in proj.get('phases', []):
                pnum = phase.get('phase', 0)
                if pnum <= comp_phase: continue
                req_type = 'next' if pnum == comp_phase + 1 else 'future'
                for req in phase.get('requirementItemIds', []):
                    if req.get('itemId') == tid:
                        needed, owned = req.get('quantity', 0), inv.get(str(pnum), {}).get(req.get('itemId'), 0)
                        if (rem := needed - owned) > 0:
                            results.append((f"{pname} (Ph{pnum}): x{rem}", req_type))
        return results

    def get_item_by_name(self, name: str): return self.items.get(name)