"""Minimal XLSX value reader for public authority tables; no spreadsheet runtime."""
import io
import posixpath
import zipfile
import xml.etree.ElementTree as ET

NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def xlsx_sheets(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist())>100_000_000:raise ValueError('XLSX zu groß')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS+'si')]
        rels={r.get('Id'):r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall(NS+'sheets/'+NS+'sheet'):
            target=rels[sh.get(REL+'id')]
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=[]
            for row in ET.fromstring(z.read(path)).findall(NS+'sheetData/'+NS+'row'):
                values={}
                for cell in row.findall(NS+'c'):
                    ref=cell.get('r');text=cell.findtext(NS+'v');typ=cell.get('t')
                    if typ=='s':value=shared[int(text)] if text is not None else None
                    elif typ=='inlineStr':value=''.join(cell.find(NS+'is').itertext())
                    else:value=text
                    values[''.join(c for c in ref if c.isalpha())]=value
                rows.append((int(row.get('r')),values))
            sheets[sh.get('name')]=rows
        return sheets
