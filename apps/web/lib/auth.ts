import {createServerSupabase} from './supabase-server';

export function authorizedEmails(){
  return (process.env.AUTHORIZED_EMAILS || '')
    .split(',')
    .map(v=>v.trim().toLowerCase())
    .filter(Boolean);
}

export function emailIsAuthorized(email?: string | null){
  if(!email) return false;
  const allowed = authorizedEmails();
  return allowed.includes(email.trim().toLowerCase());
}

export async function getAuthorizedUser(){
  const supabase = await createServerSupabase();
  const {data:{user},error} = await supabase.auth.getUser();
  if(error || !user) return {user:null,status:401 as const};
  if(!emailIsAuthorized(user.email)) return {user:null,status:403 as const};
  return {user,status:200 as const};
}
