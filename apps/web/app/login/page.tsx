'use client';
import {useState} from 'react';
import {createBrowserSupabase} from '@/lib/supabase-browser';

const GoogleMark=()=> <svg className="googleMark" viewBox="0 0 24 24" aria-hidden><path fill="currentColor" d="M21.35 12.2c0-.74-.07-1.45-.2-2.13H12v4.03h5.23a4.47 4.47 0 0 1-1.94 2.93v2.61h3.14c1.84-1.69 2.92-4.19 2.92-7.44Z"/><path fill="currentColor" opacity=".78" d="M12 21.7c2.62 0 4.82-.87 6.43-2.36l-3.14-2.61c-.87.58-1.98.93-3.29.93-2.53 0-4.67-1.71-5.44-4.01H3.31v2.69A9.7 9.7 0 0 0 12 21.7Z"/><path fill="currentColor" opacity=".56" d="M6.56 13.65A5.84 5.84 0 0 1 6.25 12c0-.57.11-1.13.31-1.65V7.66H3.31A9.7 9.7 0 0 0 2.3 12c0 1.56.37 3.03 1.01 4.34l3.25-2.69Z"/><path fill="currentColor" opacity=".9" d="M12 6.34c1.42 0 2.7.49 3.7 1.45l2.78-2.78A9.3 9.3 0 0 0 12 2.3a9.7 9.7 0 0 0-8.69 5.36l3.25 2.69C7.33 8.05 9.47 6.34 12 6.34Z"/></svg>;

export default function LoginPage(){
  const [loading,setLoading]=useState(false),[error,setError]=useState('');
  const login=async()=>{
    setLoading(true);setError('');
    try{
      const supabase=createBrowserSupabase();
      const {error}=await supabase.auth.signInWithOAuth({provider:'google',options:{redirectTo:`${window.location.origin}/auth/callback`,queryParams:{prompt:'select_account'}}});
      if(error){setError(error.message);setLoading(false)}
    }catch(e:any){setError(e?.message||'Unable to start Google sign-in');setLoading(false)}
  };
  return <main className="authShell"><section className="authCard"><div className="authBrand"><span className="authLogo"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="16" cy="16" r="10" opacity=".65"/><circle cx="16" cy="16" r="4"/><path d="M16 16 25 9"/><circle cx="25" cy="9" r="2" fill="currentColor" stroke="none"/></svg></span><div><strong>JobRadar South</strong><span>Private research dashboard</span></div></div><div className="authCopy"><div className="eyebrow">SECURE ACCESS</div><h1>Sign in to your dashboard</h1><p>Use an authorized Google account to access job matches, categories and notification settings.</p></div><button className="googleButton" onClick={login} disabled={loading}><GoogleMark/><span>{loading?'Connecting…':'Continue with Google'}</span></button>{error&&<div className="authError">{error}</div>}<p className="authFoot">Access is restricted to email addresses configured by the dashboard owner.</p></section></main>;
}
