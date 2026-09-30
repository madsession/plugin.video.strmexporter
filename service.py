import os
import xbmcaddon
import xbmcvfs

addon = xbmcaddon.Addon()

# 1. Ensure root addon_data path exists
profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
if not xbmcvfs.exists(profile_path):
    xbmcvfs.mkdir(profile_path)

# 2. Ensure strms folder exists inside profile path
strms_path = os.path.join(profile_path, "strms")
if not xbmcvfs.exists(strms_path):
    xbmcvfs.mkdir(strms_path)