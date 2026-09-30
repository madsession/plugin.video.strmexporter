import sys
import os
import json
import re
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1

def get_param(params, key, default=None):
    return params.get(key, [default])[0]

def build_url(query):
    return sys.argv[0] + '?' + urllib.parse.urlencode(query)

def strip_kodi_tags(text):
    """Remove Kodi formatting tags like [B], [/B], [COLOR...], [/COLOR]"""
    if not text:
        return ""
    return re.sub(r'\[/?(?:color|b|i|u|bold|italic|font)[^\]]*\]', '', text, flags=re.IGNORECASE).strip()

def list_root():
    """List installed video add-ons & management actions."""
    item_cfg = xbmcgui.ListItem(label="[ Settings ]")
    item_cfg.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=build_url({'action': 'configure'}), listitem=item_cfg, isFolder=False)

    addons_dir = 'special://home/addons/'
    dirs, _ = xbmcvfs.listdir(addons_dir)
    
    for folder in dirs:
        if folder.startswith('plugin.video.') and folder != ADDON_ID:
            addon_xml_path = os.path.join(addons_dir, folder, 'addon.xml')
            if xbmcvfs.exists(addon_xml_path):
                plugin_url = f"plugin://{folder}/"
                item = xbmcgui.ListItem(label=folder)
                
                export_movie = ("Export All as Movies (.strm)", f"RunPlugin({build_url({'action': 'export_folder', 'mode': 'movie', 'path': plugin_url, 'label': folder})})")
                export_tv = ("Export All as TV Shows (.strm)", f"RunPlugin({build_url({'action': 'export_folder', 'mode': 'tv', 'path': plugin_url, 'label': folder})})")
                item.addContextMenuItems([export_movie, export_tv])
                
                url = build_url({'action': 'browse', 'path': plugin_url})
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=item, isFolder=True)
                
    xbmcplugin.endOfDirectory(HANDLE)

def get_directory_items(path):
    """Retrieve virtual directory items using JSON-RPC API."""
    rpc_cmd = {
        "jsonrpc": "2.0",
        "method": "Files.GetDirectory",
        "params": {"directory": path, "media": "files"},
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(rpc_cmd))
    data = json.loads(response)
    items = data.get('result', {}).get('files', [])
    
    if not items:
        dirs, files = xbmcvfs.listdir(path)
        for d in dirs:
            items.append({'file': os.path.join(path, d) + '/', 'label': d, 'filetype': 'directory'})
        for f in files:
            items.append({'file': os.path.join(path, f), 'label': f, 'filetype': 'file'})
    return items

def browse_path(path):
    """Browse target virtual directory while preserving visual formatting tags."""
    items = get_directory_items(path)

    for entry in items:
        item_path = entry.get('file', '')
        raw_label = entry.get('label', 'Unknown')
        clean_label = strip_kodi_tags(raw_label)
        is_folder = entry.get('filetype') == 'directory' or item_path.endswith('/')

        # Uses raw_label so Kodi renders full colors, bolding, and fonts in GUI
        item = xbmcgui.ListItem(label=raw_label)
        
        if is_folder:
            export_movie = ("Export Entire Folder (Movies)", f"RunPlugin({build_url({'action': 'export_folder', 'mode': 'movie', 'path': item_path, 'label': clean_label})})")
            export_tv = ("Export Entire Folder (TV)", f"RunPlugin({build_url({'action': 'export_folder', 'mode': 'tv', 'path': item_path, 'label': clean_label})})")
            item.addContextMenuItems([export_movie, export_tv])
            url = build_url({'action': 'browse', 'path': item_path})
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=item, isFolder=True)
        else:
            export_movie = ("Export File as Movie (.strm)", f"RunPlugin({build_url({'action': 'export_single', 'mode': 'movie', 'path': item_path, 'label': clean_label})})")
            export_tv = ("Export File as TV (.strm)", f"RunPlugin({build_url({'action': 'export_single', 'mode': 'tv', 'path': item_path, 'label': clean_label})})")
            item.addContextMenuItems([export_movie, export_tv])
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=item_path, listitem=item, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def format_tv_filename(label, season_num=1, naming_choice=0):
    """
    Advanced TV Episode Renamer:
    Choice 0: Keep original label
    Choice 1: 1x01 / 1x01-02
    Choice 2: S01E01 / S01E01-E02
    """
    label = strip_kodi_tags(label)

    if naming_choice == 0:
        return label

    # Handle NxN formats like 2x01 or 02x01
    nxn_match = re.search(r'\b(\d+)x(\d+)\b', label, re.IGNORECASE)
    if nxn_match:
        s_val = int(nxn_match.group(1))
        e_val = int(nxn_match.group(2))
        clean_title = re.sub(r'\b\d+x\d+\b', '', label, flags=re.IGNORECASE).strip(' -_')
        clean_title = strip_kodi_tags(clean_title)
        if naming_choice == 1:
            code = f"{s_val}x{e_val:02d}"
        else:
            code = f"S{s_val:02d}E{e_val:02d}"
        return f"{code} - {clean_title}" if clean_title else code

    # Handle multi-episodes like "Episode 1-2" or "Episode 01-02"
    multi_match = re.search(r'(?:episode|ep|\b)\s*(\d+)\s*[-–]\s*(\d+)', label, re.IGNORECASE)
    if multi_match:
        e1 = int(multi_match.group(1))
        e2 = int(multi_match.group(2))
        clean_title = re.sub(r'(?:episode|ep)?\s*\d+\s*[-–]\s*\d+', '', label, flags=re.IGNORECASE).strip(' -_')
        clean_title = strip_kodi_tags(clean_title)
        if naming_choice == 1:
            code = f"{season_num}x{e1:02d}-{e2:02d}"
        else:
            code = f"S{season_num:02d}E{e1:02d}-E{e2:02d}"
        return f"{code} - {clean_title}" if clean_title else code

    # Handle decimal episodes like "Episode 16.5"
    dec_match = re.search(r'(?:episode|ep|\b)\s*(\d+\.\d+)', label, re.IGNORECASE)
    if dec_match:
        ep_val = dec_match.group(1)
        clean_title = re.sub(r'(?:episode|ep)?\s*\d+\.\d+', '', label, flags=re.IGNORECASE).strip(' -_')
        clean_title = strip_kodi_tags(clean_title)
        parts = ep_val.split('.')
        padded_ep = f"{int(parts[0]):02d}.{parts[1]}"
        if naming_choice == 1:
            code = f"{season_num}x{padded_ep}"
        else:
            code = f"S{season_num:02d}E{padded_ep}"
        return f"{code} - {clean_title}" if clean_title else code

    # Handle standard single episodes like "Episode 1" or "Ep 5"
    single_match = re.search(r'(?:episode|ep)\s*(\d+)', label, re.IGNORECASE)
    if single_match:
        e_val = int(single_match.group(1))
        clean_title = re.sub(r'(?:episode|ep)\s*\d+', '', label, flags=re.IGNORECASE).strip(' -_')
        clean_title = strip_kodi_tags(clean_title)
        if naming_choice == 1:
            code = f"{season_num}x{e_val:02d}"
        else:
            code = f"S{season_num:02d}E{e_val:02d}"
        return f"{code} - {clean_title}" if clean_title else code

    return label

def prompt_tv_naming_style():
    """Dialog prompt for naming structure when exporting TV Shows."""
    dialog = xbmcgui.Dialog()
    options = [
        "Keep Original Filename",
        "Format as 1x01 (Season x Episode)",
        "Format as S01E01 (Standard TV format)"
    ]
    choice = dialog.select("Select TV Filename Structure", options)
    return choice if choice != -1 else 0

def write_strm(dest_folder, label, stream_url):
    """Helper to write a single .strm file cleanly to disk."""
    label = strip_kodi_tags(label)
    clean_name = re.sub(r'[^\w\s\.-]', '', label).strip()
    if not clean_name:
        clean_name = "exported_stream"
        
    file_path = os.path.join(dest_folder, f"{clean_name}.strm")
    f = xbmcvfs.File(file_path, 'w')
    f.write(stream_url)
    f.close()

def export_single(stream_url, label, mode):
    """Export a single file with naming prompt."""
    target_setting = 'movie_path' if mode == 'movie' else 'tv_path'
    raw_setting = ADDON.getSetting(target_setting) or 'special://home/'
    export_dir = xbmcvfs.translatePath(raw_setting)
    
    if not xbmcvfs.exists(export_dir):
        xbmcvfs.mkdirs(export_dir)

    if mode == 'tv':
        naming_choice = prompt_tv_naming_style()
        season_num = int(ADDON.getSetting('season_num') or 1)
        label = format_tv_filename(label, season_num, naming_choice)

    try:
        write_strm(export_dir, label, stream_url)
        xbmcgui.Dialog().notification("STRM Exporter", f"Exported: {label}.strm", xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        xbmcgui.Dialog().notification("STRM Exporter", f"Failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

def export_folder_recursive(path, dest_dir, mode, naming_choice, season_num, progress=None, count=[0]):
    """Recursively collect and export all items inside a folder structure."""
    items = get_directory_items(path)
    
    for entry in items:
        item_path = entry.get('file', '')
        raw_label = entry.get('label', 'Unknown')
        item_label = strip_kodi_tags(raw_label)
        is_folder = entry.get('filetype') == 'directory' or item_path.endswith('/')

        if is_folder:
            sub_dest = os.path.join(dest_dir, re.sub(r'[^\w\s\.-]', '', item_label).strip())
            if not xbmcvfs.exists(sub_dest):
                xbmcvfs.mkdirs(sub_dest)
            export_folder_recursive(item_path, sub_dest, mode, naming_choice, season_num, progress, count)
        else:
            if mode == 'tv':
                item_label = format_tv_filename(item_label, season_num, naming_choice)
            write_strm(dest_dir, item_label, item_path)
            count[0] += 1
            if progress:
                progress.update(int(count[0] % 100), f"Exporting: {item_label}")

def export_folder(path, label, mode):
    """Batch export all items inside folder."""
    target_setting = 'movie_path' if mode == 'movie' else 'tv_path'
    raw_setting = ADDON.getSetting(target_setting) or 'special://home/'
    base_dir = xbmcvfs.translatePath(raw_setting)
    
    clean_folder_name = re.sub(r'[^\w\s\.-]', '', strip_kodi_tags(label)).strip()
    dest_dir = os.path.join(base_dir, clean_folder_name)
    
    if not xbmcvfs.exists(dest_dir):
        xbmcvfs.mkdirs(dest_dir)

    naming_choice = 0
    season_num = int(ADDON.getSetting('season_num') or 1)
    if mode == 'tv':
        naming_choice = prompt_tv_naming_style()

    progress = xbmcgui.DialogProgress()
    progress.create("STRM Exporter", "Scanning folder items...")
    
    try:
        count = [0]
        export_folder_recursive(path, dest_dir, mode, naming_choice, season_num, progress, count)
        progress.close()
        xbmcgui.Dialog().notification("STRM Exporter", f"Exported {count[0]} items to {clean_folder_name}", xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        progress.close()
        xbmcgui.Dialog().notification("STRM Exporter", f"Export failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

def configure_folders():
    xbmc.executebuiltin(f'Addon.OpenSettings({ADDON_ID})')

def main():
    params = urllib.parse.parse_qs(sys.argv[2][1:]) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = get_param(params, 'action')

    if action == 'browse':
        browse_path(get_param(params, 'path'))
    elif action == 'export_single':
        export_single(get_param(params, 'path'), get_param(params, 'label', 'stream'), get_param(params, 'mode', 'movie'))
    elif action == 'export_folder':
        export_folder(get_param(params, 'path'), get_param(params, 'label', 'folder'), get_param(params, 'mode', 'movie'))
    elif action == 'configure':
        configure_folders()
    else:
        list_root()

if __name__ == '__main__':
    main()