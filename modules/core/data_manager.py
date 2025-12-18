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
                            if 'en' in name_obj: item_object['name'] = str(name_obj['en']).strip()
                            item_object['names'] = name_obj
                            for lang_code, name_val in name_obj.items():
                                if name_val: choices[str(name_val).strip()] = item_object
                                    
                        elif isinstance(name_obj, str): 
                             item_name = str(name_obj).strip()
                             item_object['name'] = item_name
                             item_object['names'] = {'en': item_name}
                             choices[item_name] = item_object

                except Exception as e:
                    print(f"Error loading item file {filename}: {e}")
        return choices

class DataManager:
    def __init__(self, items):
        self.items = items
        self.item_names_lower = [name.lower() for name in self.items.keys()]
        
        self.hideout_data = self._load_json_dir(Constants.HIDEOUT_DIR)
        self.project_data = self._load_json(Constants.PROJECTS_FILE, [])
        self.trade_data = self._load_json(Constants.TRADES_FILE, [])
        self.item_to_trades_map = {}
        for trade in self.trade_data:
            item_id = trade.get('itemId')
            if item_id: self.item_to_trades_map.setdefault(item_id, []).append(trade)
        
        self.maps_data = self._load_json(Constants.MAPS_FILE, [])
        self.id_to_map = {m.get('id'): m for m in self.maps_data if m.get('id')}
            
        self.quest_data = self._load_json_dir(Constants.QUESTS_DIR)
        self.user_progress = self._load_json(Constants.PROGRESS_FILE, {})
        
        # --- NEW: Stash Data ---
        # Stash is saved in the user_progress dictionary under 'stash_inventory'
        if 'stash_inventory' not in self.user_progress:
            self.user_progress['stash_inventory'] = {}
        
        self.id_to_item_map = {}
        for item in self.items.values():
            if item.get('id'): self.id_to_item_map[item['id']] = item
        
        self.id_to_name_map = {i_id: item.get('name', 'Unknown') for i_id, item in self.id_to_item_map.items()}
        self._backup_progress()

    def _load_json(self, filepath: str, default=None):
        if not os.path.exists(filepath): return default or {}
        try: 
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default or {}

    def _load_json_dir(self, directory: str):
        data_list = []
        if not os.path.exists(directory): return data_list
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f: data_list.append(json.load(f))
                except Exception as e: print(f"Error loading data file {filename} from {directory}: {e}")
        return data_list

    def _backup_progress(self):
        if os.path.exists(Constants.PROGRESS_FILE):
            try: shutil.copy2(Constants.PROGRESS_FILE, Constants.PROGRESS_FILE + ".bak")
            except Exception: pass

    def save_user_progress(self):
        try:
            temp_file = Constants.PROGRESS_FILE + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_progress, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, Constants.PROGRESS_FILE)
        except Exception as e: print(f"Error saving progress: {e}")

    def reload_progress(self): 
        new_data = self._load_json(Constants.PROGRESS_FILE, {})
        self.user_progress.clear()
        self.user_progress.update(new_data)
        if 'stash_inventory' not in self.user_progress: self.user_progress['stash_inventory'] = {}
        self._backup_progress()
    
    # --- STASH MANAGEMENT ---
    def get_stash_count(self, item_id: str) -> int:
        return self.user_progress.get('stash_inventory', {}).get(item_id, 0)

    def set_stash_count(self, item_id: str, count: int):
        if count > 0:
            self.user_progress['stash_inventory'][item_id] = count
        else:
            if item_id in self.user_progress['stash_inventory']:
                del self.user_progress['stash_inventory'][item_id]
        self.save_user_progress()

    def get_item_note(self, item_id: str) -> str:
        return self.user_progress.get('item_notes', {}).get(item_id, "")

    def set_item_note(self, item_id: str, note: str):
        if 'item_notes' not in self.user_progress: self.user_progress['item_notes'] = {}
        if note and note.strip(): self.user_progress['item_notes'][item_id] = note.strip()
        elif item_id in self.user_progress['item_notes']: del self.user_progress['item_notes'][item_id]
        self.save_user_progress()

    def get_localized_name(self, item_identifier, lang_code='en'):
        item = None
        if isinstance(item_identifier, dict): item = item_identifier
        elif isinstance(item_identifier, str): item = self.id_to_item_map.get(item_identifier) or self.id_to_map.get(item_identifier)
        if not item: return item_identifier.replace('_', ' ').title() if isinstance(item_identifier, str) else "Unknown"
        names = item.get('names', {})
        if isinstance(names, dict) and lang_code in names: return names[lang_code]
        name_field = item.get('name')
        if isinstance(name_field, dict): return name_field.get(lang_code, name_field.get('en', 'Unknown'))
        elif isinstance(name_field, str): return name_field
        return "Unknown"

    def get_quest_map_names(self, quest_data, lang_code='en'):
        map_ids = quest_data.get('map')
        if not map_ids: return []
        if isinstance(map_ids, str): map_ids = [map_ids]
        names = []
        for mid in map_ids:
            map_obj = self.id_to_map.get(mid)
            names.append(self.get_localized_name(map_obj, lang_code) if map_obj else mid.replace('_', ' ').title())
        return names

    def get_filtered_quests(self, tracked_only: bool = False, lang_code='en'):
        if 'quests' not in self.user_progress: self.user_progress['quests'] = {}
        all_quest_info = []
        for quest in self.quest_data:
            q_id = quest.get('id')
            if not q_id: continue
            info = quest.copy()
            if isinstance(info.get('name'), dict): info['name'] = info['name'].get(lang_code, info['name'].get('en', 'Unknown'))
            original_objs, flat_objs = info.get('objectives', []), []
            for obj in original_objs:
                if isinstance(obj, dict): flat_objs.append(obj.get(lang_code, obj.get('en', 'Unknown')))
                elif isinstance(obj, str): flat_objs.append(obj)
            info['objectives'] = flat_objs
            progress = self.user_progress['quests'].get(q_id, {})
            info.update(is_completed=progress.get('quest_completed', False), is_tracked=progress.get('is_tracked', False), objectives_completed=progress.get('objectives_completed', []))
            all_quest_info.append(info)
        custom_order = self.user_progress.get('quest_order', [])
        def sort_key(q):
            q_id = q['id']
            order_index = custom_order.index(q_id) if q_id in custom_order else len(custom_order)
            return (not q['is_tracked'], order_index, q['is_completed'])
        sorted_quests = sorted(all_quest_info, key=sort_key)
        if tracked_only: return sorted([q for q in all_quest_info if q['is_tracked'] and not q['is_completed']], key=lambda q: custom_order.index(q['id']) if q['id'] in custom_order else 999)
        else: return sorted_quests



    def find_trades_for_item(self, item_name: str):
        item = self.get_item_by_name(item_name)
        return self.item_to_trades_map.get(item['id'], []) if item and 'id' in item else []
    
    def find_quest_item_requirements(self, item_name: str, lang_code='en'):
        """
        Find quest requirements for an item.
        Returns list of tuples: (display_string, is_complete)
        """
        results, target_item = [], self.get_item_by_name(item_name)
        if not target_item or 'id' not in target_item: return []
        tid = target_item['id']
        
        # Get user quest progress
        u_quests = self.user_progress.get('quests', {})
        
        for quest in self.quest_data:
            q_id = quest.get('id')
            if not q_id: continue
            
            # Skip if quest is already completed
            q_progress = u_quests.get(q_id, {})
            if q_progress.get('quest_completed', False): continue
            
            # Check requirements
            q_reqs = quest.get('requiredItemIds', [])
            for req in q_reqs:
                if req.get('itemId') == tid:
                    q_name = self.get_localized_name(quest, lang_code)
                    needed = req.get('quantity', 0)
                    
                    # Quests usually don't have a partial 'owned' count in user_progress 
                    # unless it's tracked objective-wise, but for simple items we check stash?
                    # For now, just show total needed.
                    is_complete = False # Quests are either done or not for these items usually
                    
                    display_str = f"{q_name}: x{needed}"
                    results.append((display_str, is_complete))
                    
        return results

    def find_hideout_requirements(self, item_name: str, lang_code='en'):
        """
        Find hideout upgrade requirements for an item.
        Returns list of tuples: (display_string, req_type, is_complete, needed_qty)
        """
        results, target_item = [], self.get_item_by_name(item_name)
        if not target_item or 'id' not in target_item: return []
        tid = target_item['id']
        h_inv = self.user_progress.get('hideout_inventory', {})
        for station in self.hideout_data:
            sid = station.get('id')
            sname = self.get_localized_name(station, lang_code)
            cur_lvl = self.user_progress.get(station.get('id'), 0)
            for lvl_info in station.get('levels', []):
                lvl = lvl_info.get('level', 0)
                if lvl <= cur_lvl: continue
                req_type = 'next' if lvl == cur_lvl + 1 else 'future'
                for req in lvl_info.get('requirementItemIds', []):
                    if req.get('itemId') == tid:
                        needed = req.get('quantity', 0)
                        owned = h_inv.get(sid, {}).get(str(lvl), {}).get(req.get('itemId'), 0)
                        is_complete = owned >= needed
                        if is_complete:
                            display_str = f"{sname} (Lvl {lvl}): x{needed}"
                        else:
                            remaining = needed - owned
                            display_str = f"{sname} (Lvl {lvl}): x{remaining}"
                        results.append((display_str, req_type, is_complete, needed))
        return results

    def find_project_requirements(self, item_name: str, lang_code='en'):
        """Find project/expedition requirements for an item."""
        results, target_item = [], self.get_item_by_name(item_name)
        if not target_item or 'id' not in target_item: return []
        tid = target_item['id']
        p_prog = self.user_progress.get('projects', {})
        for proj in self.project_data:
            pid = proj.get('id')
            pname = self.get_localized_name(proj, lang_code)
            if 'Project' in pname: pname = pname.replace('Project', '').strip()
            prog = p_prog.get(pid, {'completed_phase': 0, 'inventory': {}})
            comp_phase, inv = prog.get('completed_phase', 0), prog.get('inventory', {})
            for phase in proj.get('phases', []):
                pnum = phase.get('phase', 0)
                if pnum <= comp_phase: continue
                req_type = 'next' if pnum == comp_phase + 1 else 'future'
                for req in phase.get('requirementItemIds', []):
                    if req.get('itemId') == tid:
                        needed = req.get('quantity', 0)
                        owned = inv.get(str(pnum), {}).get(req.get('itemId'), 0)
                        is_complete = owned >= needed
                        if is_complete:
                            display_str = f"{pname} (Ph{pnum}): x{needed}"
                        else:
                            remaining = needed - owned
                            display_str = f"{pname} (Ph{pnum}): x{remaining}"
                        results.append((display_str, req_type, is_complete, needed))
        return results

    def get_item_by_name(self, name: str): return self.items.get(name)