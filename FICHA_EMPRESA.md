# Ficha Empresa DNPRI

## Arquitectura

GitHub Pages sirve únicamente la interfaz. El navegador reutiliza la sesión de Supabase y llama a la Edge Function `company-brief`; nunca recibe claves de investigación ni del renderizador. La función vuelve a comprobar que `usuarios_dnpri.rol` sea `administrador` o `editor`, investiga con búsqueda web, persiste borradores/versiones bajo RLS y entrega exportaciones mediante URLs firmadas de dos minutos.

El servicio privado `backend/` abre el archivo **`2026-09 Total Energies.docx` directamente como paquete DOCX**, conserva sus estilos, secciones, márgenes, encabezados, pies, recursos y relaciones, y sustituye exclusivamente textos e imagen variables. Para PDF convierte ese mismo DOCX con LibreOffice; no existe una segunda plantilla HTML.

## Despliegue

1. Aplicar `supabase/migrations/202609290001_company_briefs.sql`.
2. Desplegar la función: `supabase functions deploy company-brief`.
3. Construir el renderizador desde la raíz: `docker build -f backend/Dockerfile -t dnpri-document-renderer .` y publicarlo tras HTTPS en una red privada o con acceso restringido.
4. Configurar secretos sólo en Supabase:

   ```sh
   supabase secrets set \
     OPENAI_API_KEY=... \
     RESEARCH_MODEL=gpt-5.2 \
     DOCUMENT_RENDERER_URL=https://renderer.example \
     DOCUMENT_RENDERER_SECRET=... \
     ALLOWED_ORIGIN=https://dnpri-ied.github.io
   ```

5. Configurar el mismo `DOCUMENT_RENDERER_SECRET` como variable de entorno del contenedor.

`SUPABASE_ANON_KEY`/`SUPABASE_URL` son provistos automáticamente por Supabase. No deben agregarse secretos al frontend. La clave publicable presente en el sitio no es una clave privilegiada y todas las operaciones se protegen nuevamente mediante JWT, roles y RLS.

## Criterios editoriales

El prompt del backend obliga a priorizar sitio corporativo, Investor Relations, reporte anual, estados/presentaciones, comunicados y sitio argentino. Todo faltante se marca “Información no disponible”; cada fuente guarda título, editor, URL directa y fecha de consulta. La ficha se abre siempre como borrador editable y nunca se descarga automáticamente.

