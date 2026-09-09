import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {decryptIntegrations,encryptIntegrations,mask,IntegrationPayload} from '@/lib/integration-crypto';

const keys:(keyof IntegrationPayload)[]=['ntfy_server','ntfy_topic','telegram_bot_token','telegram_chat_id','smtp_host','smtp_port','smtp_username','smtp_password','alert_email_from','alert_email_to','gemini_api_key','gemini_model'];
const secrets=new Set<keyof IntegrationPayload>(['ntfy_topic','telegram_bot_token','smtp_password','gemini_api_key']);
const defaults:IntegrationPayload={ntfy_server:'https://ntfy.sh',smtp_host:'smtp.gmail.com',smtp_port:'587',gemini_model:'gemini-3.1-flash-lite'};

function safeView(p:IntegrationPayload){
  const merged={...defaults,...p};
  const out:any={};
  for(const k of keys){
    const v=String(merged[k]||'');
    out[k]=secrets.has(k)?'':v;
    out[`${k}_configured`]=!!v;
    out[`${k}_masked`]=v?mask(v):'';
  }
  return out;
}
async function auth(){const a=await getAuthorizedUser();return a.status===200?a:null}

export async function GET(){
  const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const {data,error}=await admin().from('integration_settings').select('encrypted_payload,masked_json,updated_at').eq('user_id',a.user!.id).maybeSingle();
  if(error)return NextResponse.json({error:error.message},{status:500});
  let p:IntegrationPayload={};
  if(data?.encrypted_payload){try{p=decryptIntegrations(data.encrypted_payload)}catch(e:any){return NextResponse.json({error:e.message},{status:500})}}
  return NextResponse.json({...safeView(p),updated_at:data?.updated_at||null});
}

export async function PATCH(req:Request){
  const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const body=await req.json().catch(()=>({}));
  const existing=await admin().from('integration_settings').select('encrypted_payload').eq('user_id',a.user!.id).maybeSingle();
  if(existing.error)return NextResponse.json({error:existing.error.message},{status:500});
  let p:IntegrationPayload={};
  if(existing.data?.encrypted_payload){try{p=decryptIntegrations(existing.data.encrypted_payload)}catch{p={}}}
  for(const k of keys){
    if(!(k in body))continue;
    const value=String(body[k]??'').trim();
    // Blank secret/non-secret values preserve the previous value unless explicitly cleared.
    if(value)(p as any)[k]=value;
  }
  for(const k of Array.isArray(body.clear_fields)?body.clear_fields:[]){if(keys.includes(k))delete p[k as keyof IntegrationPayload]}
  p={...defaults,...p};
  const masked=safeView(p);
  const {data,error}=await admin().from('integration_settings').upsert({user_id:a.user!.id,encrypted_payload:encryptIntegrations(p),masked_json:masked,updated_at:new Date().toISOString()},{onConflict:'user_id'}).select('updated_at').single();
  return NextResponse.json(error?{error:error.message}:{...masked,updated_at:data?.updated_at},{status:error?400:200});
}
