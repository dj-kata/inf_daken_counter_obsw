pyin=/mnt/c/*/Python310/Scripts/pyinstaller.exe
$pyin *.pyw --clean --noconsole --onefile --icon=icon.ico --add-data "icon.ico;./" --add-data "resources/*;./resources/" --add-data "export/*;./export/"
cp dist/notes_counter.exe /mnt/d/bin/YouTubeLive/inf_daken_counter
cp dist/notes_counter.exe inf_daken_counter
cp version.txt inf_daken_counter/
cp noteslist.pkl inf_daken_counter/
cp dp_unofficial.pkl inf_daken_counter/
cp sp_12jiriki.pkl inf_daken_counter/
cp -a layout inf_daken_counter/
cp -a resouces inf_daken_counter/
zip inf_daken_counter.zip inf_daken_counter/* inf_daken_counter/*/* inf_daken_counter/*/*/*
