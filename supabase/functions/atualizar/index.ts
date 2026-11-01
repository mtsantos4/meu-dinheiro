// Função "atualizar": dispara a rotina de cotações e proventos no GitHub Actions.
// Só aceita usuários logados no app. Segredo necessário: GH_TOKEN (token do GitHub com permissão Actions: write).
import { createClient } from "npm:@supabase/supabase-js@2";

const REPO = "mtsantos4/meu-dinheiro";
const WORKFLOW = "atualizar.yml";
const INTERVALO_MIN_SEG = 90; // evita disparos repetidos em sequência

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const resp = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const url = Deno.env.get("SUPABASE_URL")!;
    const auth = req.headers.get("Authorization") ?? "";
    const usuario = createClient(url, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
    const { data: { user } } = await usuario.auth.getUser();
    if (!user) return resp({ ok: false, erro: "não autenticado" }, 401);

    const admin = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const { data: ult } = await admin.from("mercado_docs").select("data").eq("col", "config").eq("id", "disparo").maybeSingle();
    const ultimo = ult?.data?.em ? Date.parse(ult.data.em) : 0;
    if (Date.now() - ultimo < INTERVALO_MIN_SEG * 1000) {
      return resp({ ok: true, jaEmAndamento: true, desde: ult?.data?.em });
    }

    const token = Deno.env.get("GH_TOKEN");
    if (!token) return resp({ ok: false, erro: "Segredo GH_TOKEN não configurado no Supabase" }, 500);
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "meu-dinheiro",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    if (r.status !== 204) {
      const txt = await r.text();
      return resp({ ok: false, erro: `GitHub respondeu ${r.status}: ${txt.slice(0, 200)}` }, 502);
    }
    const em = new Date().toISOString();
    await admin.from("mercado_docs").upsert({ col: "config", id: "disparo", data: { em, por: user.id } }, { onConflict: "col,id" });
    return resp({ ok: true, em });
  } catch (e) {
    return resp({ ok: false, erro: String(e) }, 500);
  }
});
