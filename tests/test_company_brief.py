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

def test_generated_brief_opens_editor_and_photo_has_safe_fallback():
    js=(ROOT/'ficha-empresa.js').read_text()
    css=(ROOT/'ficha-empresa.css').read_text()
    assert "current=normalizeBrief(data); data=current; showTab('editor')" in js
    assert ".fe-modal [hidden]{display:none!important}" in css
    assert "u.protocol==='https:'?u.href:''" in js
    assert 'fe-photo-placeholder' in js
    assert "image.onerror=()=>{frame.innerHTML=photoHtml('');}" in js

def test_all_company_brief_response_fields_are_mapped_to_editor():
    js=(ROOT/'ficha-empresa.js').read_text()
    for field in ('photo_url','name','role','nationality','education','career','tenure_functions',
                  'company_information','overview','projects'):
        assert field in js
    assert 'normalizeBrief' in js
    assert 'company_profile' in js
    assert 'presence_in_argentina' in js

def test_backend_uses_master_and_libreoffice():
    app=(ROOT/'backend/app.py').read_text()
    assert "TEMPLATE=ROOT/'2026-09 Total Energies.docx'" in app
    assert "['libreoffice','--headless'" in app
    assert "openai.com/v1/responses" in (ROOT/'supabase/functions/company-brief/index.ts').read_text()
