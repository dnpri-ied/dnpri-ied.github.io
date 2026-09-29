import hashlib
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]

def test_master_template_is_valid_and_unchanged():
    template=ROOT/'2026-09 Total Energies.docx'
    assert template.exists()
    with ZipFile(template) as docx:
        names=set(docx.namelist())
    assert {'[Content_Types].xml','word/document.xml','word/styles.xml'} <= names
    # Guardrail for the exact master supplied with this repository.
    assert hashlib.sha256(template.read_bytes()).hexdigest() == '40bbd2753e3f55178630d038a1fc427ab1d295407717f7eb3c11a4d89bf4dabb'

def test_frontend_contract_and_no_server_secrets():
    html=(ROOT/'index.html').read_text()
    js=(ROOT/'ficha-empresa.js').read_text()
    assert 'id="openFichaEmpresa"' in html
    assert all(label in html for label in ('Guardar borrador','Regenerar información','Descargar Word','Descargar PDF'))
    assert 'OPENAI_API_KEY' not in html+js
    assert "['administrador','editor']" in js

def test_backend_uses_master_and_libreoffice():
    app=(ROOT/'backend/app.py').read_text()
    assert "TEMPLATE=ROOT/'2026-09 Total Energies.docx'" in app
    assert "['libreoffice','--headless'" in app
    assert "openai.com/v1/responses" in (ROOT/'supabase/functions/company-brief/index.ts').read_text()
