import hashlib
import io
import subprocess
from pathlib import Path
from zipfile import ZipFile
import pytest

ROOT=Path(__file__).resolve().parents[1]

def require_renderer_deps():
    for module in ('fastapi','lxml','PIL','pydantic'):pytest.importorskip(module)

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
    # Regression: the former `const URL` shadowed the browser URL constructor,
    # causing every otherwise valid HTTPS photo to be rejected.
    assert "const SUPABASE_URL" in js
    assert "const URL =" not in js

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

def editable_brief(photo_url=''):
    require_renderer_deps()
    from backend.app import Brief
    return Brief(id='00000000-0000-0000-0000-000000000001',company_name='Empresa de prueba',content={
        'executive':{'name':'Nombre editado','role':'Cargo editado','full_text':'Biografía editada','photo_url':photo_url},
        'company_information':'Información corporativa editada',
        'argentina':{'overview':'Presencia argentina editada','projects':[{'title':'Proyecto editado','description':'Descripción editada'}]},
        'section_titles':{'executive':'Perfil editado','company':'Empresa editada','argentina':'Argentina editada'}
    },sources=[{'title':'Fuente oficial','url':'https://example.com/fuente','consulted_at':'2026-09-30'}])

def document_text(payload):
    from lxml import etree
    with ZipFile(io.BytesIO(payload)) as archive:
        root=etree.fromstring(archive.read('word/document.xml'))
    return ' '.join(root.itertext())

def test_docx_export_uses_current_editor_values_and_opens_without_photo():
    require_renderer_deps()
    from backend.app import create_docx
    payload=create_docx(editable_brief())
    assert len(payload)>1000
    assert payload[:2]==b'PK'
    with ZipFile(io.BytesIO(payload)) as archive:
        assert archive.testzip() is None
        assert archive.read('word/media/image2.jpeg')
    text=document_text(payload)
    for edited in ('Nombre editado','Cargo editado','Biografía editada','Información corporativa editada',
                   'Presencia argentina editada','Proyecto editado','Descripción editada','Fuente oficial'):
        assert edited in text

def test_pdf_export_returns_nonempty_openable_pdf(monkeypatch):
    require_renderer_deps()
    from backend import app as renderer
    minimal_pdf=b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'
    def convert(command,**kwargs):
        Path(command[command.index('--outdir')+1],'ficha.pdf').write_bytes(minimal_pdf)
        return subprocess.CompletedProcess(command,0,b'',b'')
    monkeypatch.setenv('DOCUMENT_RENDERER_SECRET','test-secret')
    monkeypatch.setattr(renderer.subprocess,'run',convert)
    response=renderer.render('pdf',editable_brief(),x_render_secret='test-secret')
    assert response.media_type=='application/pdf'
    assert response.body.startswith(b'%PDF-') and response.body.endswith(b'%%EOF\n')

def test_photo_download_normalizes_valid_image_and_rejects_missing_or_insecure(monkeypatch):
    require_renderer_deps()
    from backend import app as renderer
    image=renderer.Image.new('RGB',(12,12),'white');raw=io.BytesIO();image.save(raw,'PNG')
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,size):return raw.getvalue()
    monkeypatch.setattr(renderer,'urlopen',lambda request,timeout:Reply())
    assert renderer.download_photo('https://official.example/executive.png')[:2]==b'\xff\xd8'
    assert renderer.download_photo('http://official.example/executive.png') is None
    assert renderer.download_photo('') is None

def test_frontend_export_sends_editable_snapshot_and_validates_download():
    js=(ROOT/'ficha-empresa.js').read_text()
    edge=(ROOT/'supabase/functions/company-brief/index.ts').read_text()
    assert "brief=collect();await persist(brief)" in js
    assert "invoke('export',{id,format,brief})" in js
    assert "blob.slice(0,5)" in js and "'%PDF-'" in js and "header[0]===0x50" in js
    assert "body.brief?.id===body.id" in edge
    assert "type.startsWith('image/')" in edge
