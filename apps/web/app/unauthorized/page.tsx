'use client';
import {createBrowserSupabase} from '@/lib/supabase-browser';
export default function Unauthorized(){
  const leave=async()=>{const s=createBrowserSupabase();await s.auth.signOut();window.location.href='/login'};
  return <main className="authShell"><section className="authCard"><div className="authBrand"><span className="authLogo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3 4.5 6v5.4c0 4.7 3.1 8.1 7.5 9.6 4.4-1.5 7.5-4.9 7.5-9.6V6L12 3Z"/><path d="M9.5 12.2 11 13.7l3.7-3.9"/></svg></span><div><strong>JobRadar South</strong><span>Private research dashboard</span></div></div><div className="authCopy"><div className="eyebrow">ACCESS RESTRICTED</div><h1>This Google account is not authorized</h1><p>Sign out and use an email address listed in <code>AUTHORIZED_EMAILS</code> for this deployment.</p></div><button className="btn wide" onClick={leave}>Sign out</button></section></main>;
}
