"""Private document renderer. It edits the master DOCX package; it never recreates its design."""
from datetime import datetime, timezone
from copy import deepcopy
from io import BytesIO
import os, re, subprocess, tempfile, zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from lxml import etree
from PIL import Image
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/'2026-09 Total Energies.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{%s}'%NS['w']
MONTHS=('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre')
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)

class Brief(BaseModel):
    id:str
    company_name:str
    content:dict
    sources:list[dict]=[]

def authorize(secret:str|None):
    expected=os.environ.get('DOCUMENT_RENDERER_SECRET')
    if not expected or secret!=expected: raise HTTPException(401,'Unauthorized')

def paragraph_text(p): return ''.join(t.text or '' for t in p.xpath('.//w:t',namespaces=NS)).strip()
def set_paragraph(p,text):
    texts=p.xpath('.//w:t',namespaces=NS)
    if not texts: return
    texts[0].text=str('Información no disponible' if text is None else text)
    for node in texts[1:]: node.text=''

def replace_exact(root,old,new):
    for p in root.xpath('.//w:p',namespaces=NS):
        if paragraph_text(p)==old:set_paragraph(p,new)

def append_sources(root,sources):
    if not sources:return
    body=root.find('.//w:body',NS);sect=body.find('w:sectPr',NS) if body is not None else None
    if body is None:return
    def add(text,bold=False):
        p=etree.Element(W+'p');r=etree.SubElement(p,W+'r')
        if bold:
            props=etree.SubElement(r,W+'rPr');etree.SubElement(props,W+'b')
        node=etree.SubElement(r,W+'t');node.text=text
        body.insert(len(body)-1 if sect is not None else len(body),p)
    add('Fuentes consultadas',True)
    for source in sources:
        label=str(source.get('title') or source.get('publisher') or 'Fuente')
        url=str(source.get('url') or 'URL no disponible')
        consulted=str(source.get('consulted_at') or 'Información no disponible')
        add(f'{label} · consulta {consulted} · {url}')

def download_photo(url:str)->bytes|None:
    if not url or not url.startswith('https://'):return None
    req=Request(url,headers={'User-Agent':'DNPRI document renderer/1.0'})
    with urlopen(req,timeout=12) as r:
        raw=r.read(5_000_001)
    if len(raw)>5_000_000:return None
    image=Image.open(BytesIO(raw)).convert('RGB');out=BytesIO();image.thumbnail((1600,1600));image.save(out,'JPEG',quality=92);return out.getvalue()

def placeholder_photo()->bytes:
    image=Image.new('RGB',(800,960),'#eef2f6')
    out=BytesIO();image.save(out,'JPEG',quality=90);return out.getvalue()

def create_docx(brief:Brief)->bytes:
    if not TEMPLATE.is_file():raise HTTPException(500,'Master template is missing')
    src=zipfile.ZipFile(TEMPLATE);files={n:src.read(n) for n in src.namelist()};src.close()
    root=etree.fromstring(files['word/document.xml']);company=brief.company_name.strip();c=brief.content;executive=c.get('executive') or {};argentina=c.get('argentina') or {};projects=argentina.get('projects') or []
    now=datetime.now(timezone.utc);date=f'{MONTHS[now.month-1].capitalize()} {now.year}'
    for old in ('Septiembre 2026','TOTAL ENERGIES'):replace_exact(root,old,date if old.startswith('Septiembre') else company.upper())
    replace_exact(root,'SINTESIS INFORMATIVA PARA REUNIÓN BILATERAL CON TOTAL ENERGIES',f'SÍNTESIS INFORMATIVA PARA REUNIÓN BILATERAL CON {company.upper()}')
    exec_map={
      'Patrick Pouyanné':executive.get('name'),
      'Presidente y Director Ejecutivo (CEO) de TotalEnergies':executive.get('role')
    }
    for old,new in exec_map.items():replace_exact(root,old,new or 'Información no disponible')
    biography=executive.get('full_text') or '\n\n'.join(str(executive.get(k) or 'Información no disponible') for k in ('nationality','education','career','tenure_functions'))
    exec_paras=[p for p in root.xpath('.//w:p',namespaces=NS) if paragraph_text(p).startswith(('Nació en Petit-Quevilly','Pouyanné inició','En enero de 1997','En 2000, Total','En octubre de 2014','En mayo de 2015'))]
    if exec_paras:
        set_paragraph(exec_paras[0],biography)
        for p in exec_paras[1:]:set_paragraph(p,'')
    company_paras=[p for p in root.xpath('.//w:p',namespaces=NS) if paragraph_text(p).startswith(('TotalEnergies SE','Actualmente, la gran mayoría','El Estado francés','Opera en los segmentos','Tiene como objetivo'))]
    if company_paras:
        set_paragraph(company_paras[0],c.get('company_information') or 'Información no disponible')
        for p in company_paras[1:]:set_paragraph(p,'')
    titles=c.get('section_titles') or {}
    replace_exact(root,'Perfil de la contraparte',titles.get('executive') or 'Perfil de la contraparte')
    replace_exact(root,'Información de la empresa',titles.get('company') or 'Información de la empresa')
    replace_exact(root,'Total en Argentina',titles.get('argentina') or f'{company} en Argentina')
    ar_intro=next((p for p in root.xpath('.//w:p',namespaces=NS) if paragraph_text(p).startswith('TotalEnergies es actualmente')),None)
    if ar_intro is not None:set_paragraph(ar_intro,argentina.get('overview') or 'Información no disponible')
    title_prefixes=('1. Hito','2. Consolidación','3. Vaca Muerta','4. Expansión')
    titles=[p for p in root.xpath('.//w:p',namespaces=NS) if paragraph_text(p).startswith(title_prefixes)]
    descriptions=[]
    for title in titles:
        node=title.getnext()
        while node is not None and node.tag!=W+'p':node=node.getnext()
        if node is not None:descriptions.append(node)
    for i,title in enumerate(titles):
        project=projects[i] if i<len(projects) else {'title':'Información no disponible','description':'Información no disponible'}
        set_paragraph(title,f"{i+1}. {project.get('title') or 'Información no disponible'}")
        if i<len(descriptions):set_paragraph(descriptions[i],project.get('description') or 'Información no disponible')
    if titles and descriptions and len(projects)>len(titles):
        anchor=descriptions[-1]
        for i,project in enumerate(projects[len(titles):],start=len(titles)):
            extra_title=deepcopy(titles[-1]);extra_description=deepcopy(descriptions[-1])
            set_paragraph(extra_title,f"{i+1}. {project.get('title') or 'Información no disponible'}")
            set_paragraph(extra_description,project.get('description') or 'Información no disponible')
            anchor.addnext(extra_title);extra_title.addnext(extra_description);anchor=extra_description
    # A few model projects span multiple paragraphs. Remove those residual model-only
    # paragraphs while retaining every paragraph/style container in the master.
    residual_prefixes=('Es una de las primeras iniciativas','El objetivo de este desarrollo','En tal sentido, directivos','Por otra parte, la división')
    for p in root.xpath('.//w:p',namespaces=NS):
        if paragraph_text(p).startswith(residual_prefixes):set_paragraph(p,'')
    append_sources(root,brief.sources)
    files['word/document.xml']=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    try: photo=download_photo(str(executive.get('photo_url') or ''))
    except Exception: photo=None
    if 'word/media/image2.jpeg' in files:files['word/media/image2.jpeg']=photo or placeholder_photo()
    out=BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as dst:
        for name,data in files.items():dst.writestr(name,data)
    return out.getvalue()

@app.post('/render/{format}')
def render(format:str,brief:Brief,x_render_secret:str|None=Header(None)):
    authorize(x_render_secret)
    if format not in ('docx','pdf'):raise HTTPException(400,'Unsupported format')
    docx=create_docx(brief)
    if format=='docx':return Response(docx,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'ficha.docx';source.write_bytes(docx)
        try: process=subprocess.run(['libreoffice','--headless','--convert-to','pdf','--outdir',tmp,str(source)],capture_output=True,timeout=90)
        except FileNotFoundError: raise HTTPException(503,'El conversor PDF no está instalado en el servicio')
        except subprocess.TimeoutExpired: raise HTTPException(504,'La conversión a PDF excedió el tiempo disponible')
        target=Path(tmp)/'ficha.pdf'
        if process.returncode or not target.exists():raise HTTPException(500,f'Falló la conversión a PDF: {process.stderr.decode(errors="replace")[:300]}')
        return Response(target.read_bytes(),media_type='application/pdf')
