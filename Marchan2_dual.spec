# Three launchers (TPV, Administración and Servidor), one shared portable runtime and shared local data.
from pathlib import Path

a = Analysis(['tpv.py', 'admin.py', 'servidor.py'], pathex=[], binaries=[], datas=[('web', 'web')], hiddenimports=['webview','desktop'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
entries = ('tpv', 'admin', 'servidor')
common = [script for script in a.scripts if script[0] not in entries]
scripts = {name: common + [script for script in a.scripts if script[0] == name] for name in entries}
assert all(len(found) == len(common)+1 for found in scripts.values())
tpv = EXE(pyz,scripts['tpv'],[],exclude_binaries=True,name='Marchan2_TPV',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon='assets/marchan2.ico')
admin = EXE(pyz,scripts['admin'],[],exclude_binaries=True,name='Marchan2_Administracion',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon='assets/marchan2.ico')
servidor = EXE(pyz,scripts['servidor'],[],exclude_binaries=True,name='Marchan2_Servidor',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon='assets/marchan2.ico')
coll = COLLECT(tpv,admin,servidor,a.binaries,a.datas,strip=False,upx=False,name='Marchan2_v0.28')
