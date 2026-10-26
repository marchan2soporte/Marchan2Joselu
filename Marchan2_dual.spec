# Two independent launchers, one shared portable runtime and shared local data.
from pathlib import Path

a = Analysis(['tpv.py', 'admin.py'], pathex=[], binaries=[], datas=[('web', 'web')], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
common = [script for script in a.scripts if script[0] not in ('tpv', 'admin')]
tpv_scripts = common + [script for script in a.scripts if script[0] == 'tpv']
admin_scripts = common + [script for script in a.scripts if script[0] == 'admin']
assert len(tpv_scripts) == len(common)+1 and len(admin_scripts) == len(common)+1
tpv = EXE(pyz,tpv_scripts,[],exclude_binaries=True,name='Marchan2_TPV',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon='assets/marchan2.ico')
admin = EXE(pyz,admin_scripts,[],exclude_binaries=True,name='Marchan2_Administracion',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon='assets/marchan2.ico')
coll = COLLECT(tpv,admin,a.binaries,a.datas,strip=False,upx=False,name='Marchan2_v0.21')
