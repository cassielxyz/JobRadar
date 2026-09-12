import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {decryptIntegrations,encryptIntegrations,mask,IntegrationPayload} from '@/lib/integration-crypto';

const keys:(keyof IntegrationPayload)[]=['ntfy_server','ntfy_topic','telegram_bot_token','telegram_chat_id','smtp_host','smtp_port','smtp_username','smtp_password','alert_email_from','alert_email_to','gemini_api_key','gemini_model'];
const secrets=new Set<keyof IntegrationPayload>(['ntfy_topic','telegram_bot_token','smtp_password','gemini_api_key']);
const defaults:IntegrationPayload={ntfy_server:'https://ntfy.sh',smtp_host:'smtp.gmail.com',smtp_port:'587',gemini_model:'gemini-3.1-flash-lite'};
const emailRe=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function cleanText(value:unknown){
  return String(value??'').replace(/[\u0000-\u001f\u007f\u200b-\u200d\ufeff]/g,'').trim();
}
function normalizeTelegramToken(value:string){
  let v=value.trim();
  v=v.replace(/^https?:\/\/api\.telegram\.org\/bot/i,'');
  v=v.replace(/^bot(?=\d{5,20}:)/i,'');
  return v.replace(/\s+/g,'');
}
function normalizeValue(k:keyof IntegrationPayload,value:unknown,current:IntegrationPayload){
  let v=cleanText(value);
  if(k==='telegram_bot_token')v=normalizeTelegramToken(v);
  if(k==='telegram_chat_id')v=v.replace(/\s+/g,'');
  if(k==='smtp_password'&&String(current.smtp_host||defaults.smtp_host).toLowerCase().includes('gmail.com'))v=v.replace(/\s+/g,'');
  if(k==='smtp_port')v=String(Math.max(1,Math.min(65535,Number(v||587))));
  return v;
}
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

async function validateNewTelegramToken(token:string){
  if(!/^\d{5,20}:[A-Za-z0-9_-]{20,}$/.test(token))return 'Telegram bot token format is invalid. Paste the raw token from BotFather, for example 123456789:ABC...';
  try{
    const r=await fetch(`https://api.telegram.org/bot${token}/getMe`,{method:'GET',cache:'no-store',signal:AbortSignal.timeout(8000)});
    if(r.ok)return null;
    let detail='';try{const j=await r.json();detail=String(j?.description||'')}catch{}
    return `Telegram rejected this bot token${detail?`: ${detail}`:''}. Generate/copy a valid token from BotFather and try again.`;
  }catch{
    return 'Could not verify the Telegram bot token right now. Check your connection and try saving again.';
  }
}

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

  let newTelegramToken='';
  let newSmtpPassword='';
  for(const k of keys){
    if(!(k in body))continue;
    const value=normalizeValue(k,body[k],p);
    // Empty fields preserve an already configured value. Explicit removal uses clear_fields.
    if(!value)continue;
    (p as any)[k]=value;
    if(k==='telegram_bot_token')newTelegramToken=value;
    if(k==='smtp_password')newSmtpPassword=value;
  }
  for(const k of Array.isArray(body.clear_fields)?body.clear_fields:[]){if(keys.includes(k))delete p[k as keyof IntegrationPayload]}
  p={...defaults,...p};

  if(newTelegramToken){
    const telegramError=await validateNewTelegramToken(newTelegramToken);
    if(telegramError)return NextResponse.json({error:telegramError,field:'telegram_bot_token'},{status:400});
  }
  if(body.telegram_chat_id&&p.telegram_chat_id&&!/^-?\d+$|^@[A-Za-z0-9_]{5,}$/.test(String(p.telegram_chat_id))){
    return NextResponse.json({error:'Telegram chat ID must be a numeric chat/group ID or a public @channel username.',field:'telegram_chat_id'},{status:400});
  }
  const gmail=String(p.smtp_host||'').toLowerCase().includes('gmail.com');
  if(newSmtpPassword&&gmail&&!/^[A-Za-z0-9]{16}$/.test(newSmtpPassword)){
    return NextResponse.json({error:'For Gmail, use the 16-character Google App Password. Spaces are removed automatically; do not use your normal Gmail password.',field:'smtp_password'},{status:400});
  }
  for(const field of ['smtp_username','alert_email_from','alert_email_to'] as const){
    if(body[field]&&p[field]&&!emailRe.test(String(p[field])))return NextResponse.json({error:`${field.replaceAll('_',' ')} is not a valid email address.`,field},{status:400});
  }

  const masked=safeView(p);
  const {data,error}=await admin().from('integration_settings').upsert({user_id:a.user!.id,encrypted_payload:encryptIntegrations(p),masked_json:masked,updated_at:new Date().toISOString()},{onConflict:'user_id'}).select('updated_at').single();
  return NextResponse.json(error?{error:error.message}:{...masked,updated_at:data?.updated_at,synced:true},{status:error?400:200});
}
