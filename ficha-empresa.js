(() => {
  'use strict';
  const URL = 'https://lrlioufcjzqbpeiigtxr.supabase.co';
  const KEY = 'sb_publishable_yiZ7cH1Ss8V5VL1tuYs38g_iN2zyKMb';
  const db = window.supabase?.createClient(URL, KEY);
  const $ = id => document.getElementById(id);
  const modal = $('fichaEmpresaModal');
  if (!modal || !db) return;
  let current = null;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const safeUrl = value => { try { const u=new URL(String(value)); return u.protocol==='https:'?u.href:''; } catch { return ''; } };
  const unavailable = 'Información no disponible';
  const useful = value => value !== undefined && value !== null && String(value).trim() && String(value).trim().toLowerCase() !== unavailable.toLowerCase();
  const asText = value => {
    if (Array.isArray(value)) return value.map(asText).filter(useful).join('\n');
    if (value && typeof value === 'object') return Object.values(value).map(asText).filter(useful).join('\n');
    return useful(value) ? String(value).trim() : '';
  };
  const firstText = (...values) => values.map(asText).find(useful) || '';
  function normalizeBrief(brief={}) {
    const raw=brief.content||{},executive=raw.executive||raw.executive_profile||raw.counterpart||{};
    const argentina=raw.argentina||raw.argentina_presence||raw.presence_in_argentina||{};
    const projects=argentina.projects||raw.projects||raw.investments||[];
    const biography=firstText(executive.full_text,executive.biography,executive.bio)||[
      ['Nacionalidad',firstText(executive.nationality)],
      ['Formación',firstText(executive.education)],
      ['Trayectoria',firstText(executive.career,executive.experience)],
      ['Antigüedad y funciones',firstText(executive.tenure_functions,executive.tenure,executive.functions)]
    ].filter(([,value])=>value).map(([label,value])=>`${label}: ${value}`).join('\n\n');
    return {...brief,company_name:firstText(brief.company_name,brief.company,brief.empresa)||unavailable,content:{...raw,
      executive:{...executive,photo_url:safeUrl(firstText(executive.photo_url,executive.photo,executive.image_url)),name:firstText(executive.name,executive.full_name)||unavailable,role:firstText(executive.role,executive.title,executive.position)||unavailable,full_text:biography||unavailable},
      company_information:firstText(raw.company_information,raw.company,raw.company_profile,raw.corporate_information)||unavailable,
      argentina:{...argentina,overview:firstText(argentina.overview,argentina.summary,argentina.description,raw.argentina_overview)||unavailable,projects:(Array.isArray(projects)?projects:[]).map(project=>typeof project==='string'?{title:'Proyecto',description:project}:{...project,title:firstText(project.title,project.name)||'Proyecto',description:firstText(project.description,project.details,project.summary)||unavailable})},
      section_titles:raw.section_titles||{}
    },sources:Array.isArray(brief.sources)?brief.sources:[]};
  }
  const notice = (message, error = false) => { const el=$('feNotice'); el.textContent=message; el.className=`fe-notice visible${error?' error':''}`; };
  const busy = value => { $('feGenerate').disabled=value; $('feSave').disabled=value; $('feRegenerate').disabled=value; $('feWord').disabled=value; $('fePdf').disabled=value; };
  async function invoke(action, body = {}) {
    const {data,error}=await db.functions.invoke('company-brief',{body:{action,...body}});
    if(error) throw new Error(error.context?.body ? await error.context.text() : error.message);
    if(data?.error) throw new Error(data.error);
    return data;
  }
  async function assertRole() {
    const {data:{user}}=await db.auth.getUser();
    if(!user) throw new Error('Debés iniciar sesión para utilizar Ficha Empresa.');
    const {data}=await db.from('usuarios_dnpri').select('rol,activo').eq('email',user.email).maybeSingle();
    if(!data?.activo || !['administrador','editor'].includes(String(data.rol).toLowerCase())) throw new Error('Esta función está habilitada sólo para Administradores y Editores.');
  }
  function section(title, key, content, removable=false) {
    return `<article class="fe-section" data-key="${escapeHtml(key)}"><div class="fe-section-bar"><h3 contenteditable="true">${escapeHtml(title)}</h3><button class="fe-icon-btn" data-move="up" title="Subir sección">↑</button><button class="fe-icon-btn" data-move="down" title="Bajar sección">↓</button>${removable?'<button class="fe-icon-btn" data-remove title="Eliminar">Eliminar</button>':''}</div><div class="fe-edit" contenteditable="true">${escapeHtml(content||'Información no disponible')}</div></article>`;
  }
  function render(data) {
    current=normalizeBrief(data); data=current; showTab('editor'); $('feEmpty').hidden=true; $('feWorkspace').hidden=false;
    $('feDocumentTitle').textContent=`SÍNTESIS INFORMATIVA PARA REUNIÓN BILATERAL CON ${data.company_name.toUpperCase()}`;
    const executive=data.content.executive||{},titles=data.content.section_titles||{};
    const projects=data.content.argentina?.projects||[];
    $('feSections').innerHTML=`
      <article class="fe-section" data-key="executive"><div class="fe-section-bar"><h3 contenteditable="true">${escapeHtml(titles.executive||'Perfil de la contraparte')}</h3><button class="fe-icon-btn" data-move="up">↑</button><button class="fe-icon-btn" data-move="down">↓</button></div><div class="fe-photo"><div id="feExecutivePhotoFrame">${photoHtml(executive.photo_url)}</div><div><input id="fePhotoUrl" value="${escapeHtml(executive.photo_url)}" placeholder="URL HTTPS de fotografía oficial"><input id="feExecutiveName" value="${escapeHtml(executive.name)}" aria-label="Nombre del ejecutivo"><input id="feExecutiveRole" value="${escapeHtml(executive.role)}" aria-label="Cargo del ejecutivo"><div class="fe-edit" contenteditable="true">${escapeHtml(executive.full_text)}</div></div></div></article>
      ${section(titles.company||'Información de la empresa','company',data.content.company_information)}
      ${section(titles.argentina||`${data.company_name} en Argentina`,'argentina',data.content.argentina?.overview)}
      <article class="fe-section" data-key="projects"><div class="fe-section-bar"><h3 contenteditable="true">${escapeHtml(titles.projects||'Principales proyectos e inversiones')}</h3><button class="fe-icon-btn" data-move="up">↑</button><button class="fe-icon-btn" data-move="down">↓</button></div><div id="feProjects">${projects.map((p,i)=>projectHtml(p,i)).join('')}</div><button class="fe-add" id="feAddProject" type="button">+ Agregar proyecto</button></article>`;
    $('feSources').innerHTML=(data.sources||[]).map(s=>{const url=safeUrl(s.url);return `<div class="fe-source"><strong>${escapeHtml(s.title||s.publisher||'Fuente')}</strong> · consulta ${escapeHtml(s.consulted_at||'Información no disponible')}<br>${url?`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`:'URL no disponible'}</div>`}).join('')||'<div class="fe-source">Información no disponible</div>';
    bindEditor();
  }
  function photoHtml(url){const safe=safeUrl(url);return safe?`<img id="feExecutivePhoto" src="${escapeHtml(safe)}" alt="Fotografía del ejecutivo">`:'<div class="fe-photo-placeholder" role="img" aria-label="Fotografía institucional no disponible"><span>DNPRI</span><small>Fotografía no disponible</small></div>';}
  function updatePhoto(value){const frame=$('feExecutivePhotoFrame');if(!frame)return;frame.innerHTML=photoHtml(value);const image=$('feExecutivePhoto');if(image)image.onerror=()=>{frame.innerHTML=photoHtml('');};}
  function projectHtml(p={},i=0){return `<div class="fe-project"><span class="fe-project-tools"><button class="fe-icon-btn" data-project-up>↑</button><button class="fe-icon-btn" data-project-down>↓</button><button class="fe-icon-btn" data-project-remove>Eliminar</button></span><h4 contenteditable="true">${i+1}. ${escapeHtml(p.title||'Nuevo proyecto')}</h4><div class="fe-edit" contenteditable="true">${escapeHtml(p.description||'Información no disponible')}</div></div>`;}
  function renumber(){[...$('feProjects').children].forEach((p,i)=>{const h=p.querySelector('h4');h.textContent=`${i+1}. ${h.textContent.replace(/^\d+\.\s*/, '')}`;});}
  function bindEditor(){
    $('fePhotoUrl').oninput=e=>updatePhoto(e.target.value);
    $('feAddProject').onclick=()=>{$('feProjects').insertAdjacentHTML('beforeend',projectHtml({},$('feProjects').children.length));bindEditor();};
    modal.querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>{const s=b.closest('.fe-section');if(b.dataset.move==='up'&&s.previousElementSibling)s.parentNode.insertBefore(s,s.previousElementSibling);if(b.dataset.move==='down'&&s.nextElementSibling)s.parentNode.insertBefore(s.nextElementSibling,s);});
    modal.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>b.closest('.fe-section').remove());
    modal.querySelectorAll('[data-project-remove]').forEach(b=>b.onclick=()=>{b.closest('.fe-project').remove();renumber();});
    modal.querySelectorAll('[data-project-up]').forEach(b=>b.onclick=()=>{const p=b.closest('.fe-project');if(p.previousElementSibling)p.parentNode.insertBefore(p,p.previousElementSibling);renumber();});
    modal.querySelectorAll('[data-project-down]').forEach(b=>b.onclick=()=>{const p=b.closest('.fe-project');if(p.nextElementSibling)p.parentNode.insertBefore(p.nextElementSibling,p);renumber();});
  }
  function collect(){
    const byKey=key=>$(`feSections`).querySelector(`[data-key="${key}"] .fe-edit`)?.innerText.trim()||'Información no disponible';
    const sectionTitles=Object.fromEntries([...$('feSections').children].map(x=>[x.dataset.key,x.querySelector('.fe-section-bar h3')?.innerText.trim()||'']));
    return {...current,content:{...current.content,executive:{...(current.content.executive||{}),photo_url:safeUrl($('fePhotoUrl')?.value.trim()),name:$('feExecutiveName')?.value.trim()||'Información no disponible',role:$('feExecutiveRole')?.value.trim()||'Información no disponible',full_text:byKey('executive')},company_information:byKey('company'),argentina:{overview:byKey('argentina'),projects:[...$('feProjects').querySelectorAll('.fe-project')].map(p=>({title:p.querySelector('h4').innerText.replace(/^\d+\.\s*/,''),description:p.querySelector('.fe-edit').innerText.trim()||'Información no disponible'}))},section_titles:sectionTitles,section_order:[...$('feSections').children].map(x=>x.dataset.key)}};
  }
  async function generate(regenerate=false){
    try{await assertRole();if(regenerate&&!confirm('La regeneración puede reemplazar el contenido visible. ¿Deseás guardar primero tus cambios manuales? Seleccioná Cancelar para volver y guardarlos.'))return;busy(true);notice('Investigando fuentes corporativas oficiales. Esto puede demorar unos minutos…');const company=regenerate?current.company_name:$('feCompany').value.trim();if(!company)throw new Error('Ingresá el nombre de la empresa.');const data=await invoke('generate',{company,brief_id:regenerate?current.id:null});render(data.brief);notice('Ficha generada. Revisá y editá el contenido antes de descargar.');await loadHistory();}catch(e){notice(e.message||'No fue posible generar la ficha.',true);}finally{busy(false);}
  }
  async function save(){try{busy(true);const data=await invoke('save',{brief:collect()});current=data.brief;notice('Borrador guardado correctamente.');await loadHistory();}catch(e){notice(e.message,true);}finally{busy(false);}}
  async function loadHistory(){try{const data=await invoke('history');$('feHistory').innerHTML=(data.briefs||[]).map(x=>`<tr><td>${escapeHtml(x.company_name)}</td><td>${new Date(x.updated_at).toLocaleString('es-AR')}</td><td>${escapeHtml(x.user_email)}</td><td><span class="fe-status">${escapeHtml(x.status)}</span></td><td><button data-open="${x.id}">Abrir/Editar</button> · <button data-download="${x.id}">Descargar</button></td></tr>`).join('')||'<tr><td colspan="5">No hay fichas generadas.</td></tr>';document.querySelectorAll('[data-open]').forEach(b=>b.onclick=async()=>{const d=await invoke('get',{id:b.dataset.open});render(d.brief);showTab('editor');});document.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>exportFile('docx',b.dataset.download));}catch(e){notice(e.message,true);}}
  async function exportFile(format,id=current?.id){try{if(!id)return;busy(true);if(id===current?.id)await save();const result=await invoke('export',{id,format});const a=document.createElement('a');a.href=result.url;a.download=result.filename;a.rel='noopener';document.body.appendChild(a);a.click();a.remove();}catch(e){notice(e.message,true);}finally{busy(false);}}
  function showTab(name){document.querySelectorAll('[data-fe-tab]').forEach(b=>b.classList.toggle('active',b.dataset.feTab===name));$('feEditorView').hidden=name!=='editor';$('feHistoryView').hidden=name!=='history';if(name==='history')loadHistory();}
  $('openFichaEmpresa').onclick=async()=>{try{await assertRole();modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';$('feCompany').focus();loadHistory();}catch(e){alert(e.message);}};
  $('closeFichaEmpresa').onclick=()=>{modal.classList.remove('open');modal.setAttribute('aria-hidden','true');document.body.style.overflow='';};
  modal.onclick=e=>{if(e.target===modal)$('closeFichaEmpresa').click();};
  $('feGenerateForm').onsubmit=e=>{e.preventDefault();generate(false);};$('feSave').onclick=save;$('feRegenerate').onclick=()=>generate(true);$('feWord').onclick=()=>exportFile('docx');$('fePdf').onclick=()=>exportFile('pdf');document.querySelectorAll('[data-fe-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.feTab));
})();
