"""Write the version resource embedded by PyInstaller."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from updater import VERSION, version_tuple

version = version_tuple(VERSION)
numeric = version[0], version[1], version[2], version[3] or version[5]
Path(sys.argv[1]).write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric}, prodvers={numeric}, mask=63, flags={2 if version[4] < 3 else 0},
                    OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', 'JARVIS'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'JARVIS'),
      StringStruct('OriginalFilename', 'JARVIS.exe'),
      StringStruct('ProductName', 'JARVIS'),
      StringStruct('ProductVersion', '{VERSION}')
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
