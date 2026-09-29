import { createClient } from '@supabase/supabase-js';

const cors={
  'Access-Control-Allow-Origin': Deno.env.get('ALLOWED_ORIGIN') || 'https://dnpri-ied.github.io',
  'Access-Control-Allow-Headers':'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods':'POST, OPTIONS'
};
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{...cors,'content-type':'application/json'}});
const unavailable='Información no disponible';

Deno.serve(async req=>{
  if(req.method==='OPTIONS') return new Response('ok',{headers:cors});
  try{
    const auth=req.headers.get('Authorization'); if(!auth) return json({error:'Sesión requerida.'},401);
    const url=Deno.env.get('SUPABASE_URL')!, anon=Deno.env.get('SUPABASE_ANON_KEY')!;
    const client=createClient(url,anon,{global:{headers:{Authorization:auth}}});
    const {data:{user}}=await client.auth.getUser(); if(!user) return json({error:'Sesión inválida.'},401);
    const {data:profile}=await client.from('usuarios_dnpri').select('rol,activo').eq('email',user.email).maybeSingle();
    if(!profile?.activo||!['administrador','editor'].includes(String(profile.rol).toLowerCase())) return json({error:'Permiso insuficiente.'},403);
    const body=await req.json(), action=body.action;
    if(action==='history'){
      const {data,error}=await client.from('fichas_empresa').select('id,empresa,estado,usuario_email,actualizado_en').order('actualizado_en',{ascending:false}); if(error)throw error;
      return json({briefs:(data||[]).map(x=>({id:x.id,company_name:x.empresa,status:x.estado,user_email:x.usuario_email,updated_at:x.actualizado_en}))});
    }
    if(action==='get') return await getBrief(client,body.id);
    if(action==='save'){
      const b=body.brief;if(!b?.id) return json({error:'Ficha inválida.'},400);
      const payload={empresa:b.company_name,estado:'borrador',contenido:b.content,fuentes:b.sources,actualizado_en:new Date().toISOString()};
      const {data,error}=await client.from('fichas_empresa').update(payload).eq('id',b.id).select().single();if(error)throw error;
      await client.from('fichas_empresa_versiones').insert({ficha_id:b.id,contenido:b.content,fuentes:b.sources,creado_por:user.id});
      return json({brief:normalize(data)});
    }
    if(action==='generate'){
      const company=String(body.company||'').trim().slice(0,160);if(!company)return json({error:'Ingresá una empresa.'},400);
      const researched=await research(company);
      let query=client.from('fichas_empresa');
      const payload={empresa:company,contenido:researched.content,fuentes:researched.sources,estado:'borrador',creado_por:user.id,usuario_email:user.email,actualizado_en:new Date().toISOString()};
      const result=body.brief_id?await query.update(payload).eq('id',body.brief_id).select().single():await query.insert(payload).select().single();
      if(result.error)throw result.error;
      await client.from('fichas_empresa_versiones').insert({ficha_id:result.data.id,contenido:researched.content,fuentes:researched.sources,creado_por:user.id});
      return json({brief:normalize(result.data)});
    }
    if(action==='export'){
      if(!['docx','pdf'].includes(body.format))return json({error:'Formato inválido.'},400);
      const {data:b,error}=await client.from('fichas_empresa').select('*').eq('id',body.id).single();if(error)throw error;
      const renderer=Deno.env.get('DOCUMENT_RENDERER_URL'),secret=Deno.env.get('DOCUMENT_RENDERER_SECRET');
      if(!renderer||!secret)return json({error:'El servicio de documentos no está configurado.'},503);
      const response=await fetch(`${renderer}/render/${body.format}`,{method:'POST',headers:{'content-type':'application/json','x-render-secret':secret},body:JSON.stringify(normalize(b))});
      if(!response.ok)throw new Error(`No se pudo generar el documento (${response.status}).`);
      const filename=`${slug(b.empresa)}-${new Date().toISOString().slice(0,10)}.${body.format}`,path=`${user.id}/${crypto.randomUUID()}-${filename}`;
      const bytes=await response.arrayBuffer();const mime=body.format==='pdf'?'application/pdf':'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      const {error:uploadError}=await client.storage.from('fichas-empresa').upload(path,bytes,{contentType:mime});if(uploadError)throw uploadError;
      const {data:signed,error:signedError}=await client.storage.from('fichas-empresa').createSignedUrl(path,120,{download:filename});if(signedError)throw signedError;
      return json({url:signed.signedUrl,filename});
    }
    return json({error:'Acción desconocida.'},400);
  }catch(error){console.error(error);return json({error:error instanceof Error?error.message:'Error interno.'},500);}
});

function normalize(x:any){return{id:x.id,company_name:x.empresa,status:x.estado,user_email:x.usuario_email,updated_at:x.actualizado_en,content:x.contenido,sources:x.fuentes};}
async function getBrief(client:any,id:string){const {data,error}=await client.from('fichas_empresa').select('*').eq('id',id).single();if(error)throw error;return json({brief:normalize(data)});}
function slug(s:string){return s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');}
async function research(company:string){
  const key=Deno.env.get('OPENAI_API_KEY');if(!key)throw new Error('El servicio de investigación no está configurado.');
  const schema={type:'object',additionalProperties:false,required:['content','sources'],properties:{content:{type:'object',additionalProperties:false,required:['executive','company_information','argentina'],properties:{executive:{type:'object',additionalProperties:false,required:['photo_url','name','role','nationality','education','career','tenure_functions'],properties:Object.fromEntries(['photo_url','name','role','nationality','education','career','tenure_functions'].map(k=>[k,{type:'string'}]))},company_information:{type:'string'},argentina:{type:'object',additionalProperties:false,required:['overview','projects'],properties:{overview:{type:'string'},projects:{type:'array',items:{type:'object',additionalProperties:false,required:['title','description'],properties:{title:{type:'string'},description:{type:'string'}}}}}}}},sources:{type:'array',items:{type:'object',additionalProperties:false,required:['title','publisher','url','consulted_at'],properties:{title:{type:'string'},publisher:{type:'string'},url:{type:'string'},consulted_at:{type:'string'}}}}}};
  const prompt=`Investigá y redactá en español una Ficha Empresa DNPRI sobre ${company}. Priorizá estrictamente: web oficial, Investor Relations, último Annual Report, estados financieros/presentaciones, comunicados oficiales y web oficial argentina. Sólo para vacíos de Argentina usá fuentes públicas confiables. No inventes ni infieras: escribí exactamente "${unavailable}" en todo dato ausente. Perfil: CEO/presidente por defecto, fotografía oficial, nombre, cargo, nacionalidad, formación, trayectoria, antigüedad y funciones. Empresa: denominación, origen, sede, fundación, descripción, segmentos, países, propiedad/accionistas, empleados, últimos ingresos, EBITDA, resultado neto, indicadores y estrategia, indicando ejercicio y moneda. Argentina: llegada, sociedades, actividades, activos, proyectos, inversiones, anuncios, desarrollo y RIGI. Proyectos principales numerados. Cada afirmación relevante debe estar respaldada por una entrada en sources con URL directa y fecha de consulta ${new Date().toISOString().slice(0,10)}. Evitá prensa si existe fuente primaria.`;
  const response=await fetch('https://api.openai.com/v1/responses',{method:'POST',headers:{authorization:`Bearer ${key}`,'content-type':'application/json'},body:JSON.stringify({model:Deno.env.get('RESEARCH_MODEL')||'gpt-5.2',tools:[{type:'web_search'}],input:prompt,text:{format:{type:'json_schema',name:'company_brief',strict:true,schema}}})});
  if(!response.ok)throw new Error(`Falló la investigación (${response.status}).`);const result=await response.json();
  const text=result.output?.flatMap((x:any)=>x.content||[]).find((x:any)=>x.type==='output_text')?.text;if(!text)throw new Error('La investigación no devolvió contenido.');return JSON.parse(text);
}
