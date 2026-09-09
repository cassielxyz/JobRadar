import crypto from 'node:crypto';

export type IntegrationPayload={
  ntfy_server?:string;
  ntfy_topic?:string;
  telegram_bot_token?:string;
  telegram_chat_id?:string;
  smtp_host?:string;
  smtp_port?:string;
  smtp_username?:string;
  smtp_password?:string;
  alert_email_from?:string;
  alert_email_to?:string;
  gemini_api_key?:string;
  gemini_model?:string;
};

function key(){
  const seed=process.env.SUPABASE_SERVICE_ROLE_KEY||'';
  if(!seed)throw new Error('SUPABASE_SERVICE_ROLE_KEY is required for integration encryption.');
  return crypto.createHash('sha256').update(seed).digest();
}
const b64=(b:Buffer)=>b.toString('base64url');
const ub64=(s:string)=>Buffer.from(s,'base64url');

export function encryptIntegrations(payload:IntegrationPayload){
  const iv=crypto.randomBytes(12);
  const cipher=crypto.createCipheriv('aes-256-gcm',key(),iv);
  const body=Buffer.concat([cipher.update(JSON.stringify(payload),'utf8'),cipher.final()]);
  const tag=cipher.getAuthTag();
  return `v1.${b64(iv)}.${b64(body)}.${b64(tag)}`;
}
export function decryptIntegrations(envelope?:string|null):IntegrationPayload{
  if(!envelope)return {};
  const [version,ivS,bodyS,tagS]=envelope.split('.');
  if(version!=='v1'||!ivS||!bodyS||!tagS)throw new Error('Invalid integration settings envelope.');
  const decipher=crypto.createDecipheriv('aes-256-gcm',key(),ub64(ivS));
  decipher.setAuthTag(ub64(tagS));
  return JSON.parse(Buffer.concat([decipher.update(ub64(bodyS)),decipher.final()]).toString('utf8'));
}
export function mask(value?:string){
  const v=(value||'').trim();
  if(!v)return '';
  if(v.includes('@')){const [a,d]=v.split('@');return `${a.slice(0,2)}•••@${d}`}
  return v.length<=6?'••••••':`${v.slice(0,3)}••••${v.slice(-3)}`;
}
