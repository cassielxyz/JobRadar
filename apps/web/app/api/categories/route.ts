import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';

async function guard(){const a=await getAuthorizedUser();if(a.status!==200)return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});return null}
export async function GET(){const denied=await guard();if(denied)return denied;const {data,error}=await admin().from('categories').select('*').order('created_at');return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});}
export async function POST(req:Request){const denied=await guard();if(denied)return denied;const body=await req.json();const {data,error}=await admin().from('categories').insert(body).select().single();return NextResponse.json(error?{error:error.message}:data,{status:error?400:201});}
export async function PATCH(req:Request){const denied=await guard();if(denied)return denied;const body=await req.json();const {id,...changes}=body;const {data,error}=await admin().from('categories').update({...changes,updated_at:new Date().toISOString()}).eq('id',id).select().single();return NextResponse.json(error?{error:error.message}:data,{status:error?400:200});}
