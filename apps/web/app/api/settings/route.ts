import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
async function guard(){const a=await getAuthorizedUser();if(a.status!==200)return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});return null}
export async function GET(){const denied=await guard();if(denied)return denied;const {data,error}=await admin().from('notification_settings').select('*').eq('id','default').single();return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});}
export async function PATCH(req:Request){const denied=await guard();if(denied)return denied;const body=await req.json();const {data,error}=await admin().from('notification_settings').update({...body,updated_at:new Date().toISOString()}).eq('id','default').select().single();return NextResponse.json(error?{error:error.message}:data,{status:error?400:200});}
