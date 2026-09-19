const BOARDS=['linkedin.com','naukri.com','indeed.com','foundit.in','shine.com','timesjobs.com','freshersworld.com','internshala.com','cutshort.io','instahyre.com','hirist.tech','iimjobs.com','apna.co','workindia.in','jobhai.com','unstop.com','wellfound.com','glassdoor.co.in','jooble.org','adzuna.in','careerjet.co.in','jora.com','talent.com','grabjobs.co','simplyhired.com','startup.jobs','remoteok.com','weworkremotely.com'];
const ATS=['greenhouse.io','lever.co','ashbyhq.com','smartrecruiters.com','myworkdayjobs.com','workable.com','recruitee.com','icims.com','taleo.net','successfactors.com'];
const SHORT=['bit.ly','tinyurl.com','t.co','cutt.ly','rb.gy','shorturl.at','rebrand.ly'];
const payment=/\b(training fee|registration fee|security deposit|refundable deposit|processing fee|pay(?:ment)?\s+(?:before|to\s+(?:the\s+)?recruiter)|send\s+money|gift\s*card|crypto(?:currency)?\s+payment|upi\s+(?:payment|transfer)|bank\s+transfer\s+to\s+(?:the\s+)?recruiter)\b/i;
const offPlatform=/\b(?:apply|send\s+(?:your\s+)?resume|contact)\b[\s\S]{0,90}\b(?:whatsapp|telegram)\b|\b(?:whatsapp|telegram)\b[\s\S]{0,90}\b(?:apply|resume|job)\b/i;
const tooGood=/\b(no interview|guaranteed job|guaranteed selection|instant joining without interview)\b/i;
const personal=/\b[A-Z0-9._%+-]+@(gmail|yahoo|outlook|hotmail|protonmail)\.[A-Z]{2,}\b/i;
const host=(u:string)=>{try{return new URL(u||'').hostname.toLowerCase().replace(/^www\./,'')}catch{return ''}};
const matches=(h:string,ds:string[])=>ds.some(d=>h===d||h.endsWith('.'+d));
const nonJobPath=/(?:^|\/)(?:legal(?:\/|$)|help(?:\/|$)|privacy(?:\/|$)|accessibility(?:\/|$)|cookie(?:s|\/|$)|terms(?:\/|$)|user-agreement(?:\/|$)|authwall(?:\/|$)|checkpoint(?:\/|$)|signup(?:\/|$)|sign-?in(?:\/|$)|login(?:\/|$)|registration(?:\/|$)|register(?:\/|$)|account(?:\/|$)|profile(?:\/|$)|feed(?:\/|$)|about(?:\/|$)|contact(?:\/|$)|support(?:\/|$))/i;
const jobish=/(job|jobs|job-listing|job-listings|viewjob|position|opening|vacanc|career|internship|intern|apply)/i;
function badJobUrl(u:string){
  if(!String(u||'').trim())return false;
  try{
    const x=new URL(u);const h=x.hostname.toLowerCase().replace(/^www\./,'');const p=x.pathname||'/';const q=x.search.toLowerCase();
    if(nonJobPath.test(p)||/(user-agreement|privacy-policy|terms-of-service|auth-button_user-agreement|login|signup|registration)/i.test(q))return true;
    if(h==='linkedin.com'||h.endsWith('.linkedin.com'))return !/^\/jobs\/view\/[^/?#]+\/?$/i.test(p);
    if(matches(h,BOARDS)&&!jobish.test(`${p}?${q}`))return true;
    return false;
  }catch{return true}
}

export function assessJobTrust(job:any,categoryType=''){
  const primary=job?.apply_url||job?.canonical_url||job?.source_url||'';
  const h=host(primary);
  const sh=host(job?.source_url||'');
  const text=`${job?.title||''} ${job?.company||''} ${job?.description||''}`;
  const reasons:string[]=[];
  const official=!!job?.official_verified||h.endsWith('.gov.in')||h.endsWith('.nic.in')||h.endsWith('.ac.in');
  const ats=matches(h,ATS),board=matches(h,BOARDS)||matches(sh,BOARDS);

  // Never trust a bad destination just because an older row once had apply_verified=true.
  if(job?.apply_url&&badJobUrl(job.apply_url))return {score:0,blocked:true,reasons:['application URL is not a concrete job page']};
  // If discovery/source pages are bad, allow the row only when there is a separate good apply URL.
  if((badJobUrl(job?.canonical_url||'')||badJobUrl(job?.source_url||''))&&(!job?.apply_url||badJobUrl(job.apply_url))){
    return {score:0,blocked:true,reasons:['source URL is not a concrete job listing']};
  }

  let score=official?97:ats?92:job?.apply_verified?86:board?76:58;
  reasons.push(official?'official/public-sector domain':ats?'recognized employer ATS':job?.apply_verified?'verified application destination':board?'recognized job platform':'unrecognized employer/source domain');
  if(matches(h,SHORT)||matches(sh,SHORT)){score-=30;reasons.push('shortened destination URL')}
  if(categoryType!=='government'&&payment.test(text))return {score:0,blocked:true,reasons:[...reasons,'requests payment/deposit from applicant']};
  if(offPlatform.test(text)&&!job?.apply_verified&&!official)return {score:15,blocked:true,reasons:[...reasons,'application routed only through WhatsApp/Telegram']};
  if(tooGood.test(text)){score-=35;reasons.push('guaranteed/no-interview claim')}
  const company=String(job?.company||'').trim().toLowerCase();
  if(!company||['unknown','unknown company','web discovery','external job-platform discovery'].includes(company)){score-=10;reasons.push('employer identity not established')}
  if(personal.test(text)&&!(official||ats||job?.apply_verified)){score-=15;reasons.push('personal-email recruiting contact')}
  if(job?.raw?.discovery_only&&!job?.apply_verified){score-=4;reasons.push('third-party discovery listing')}
  score=Math.max(0,Math.min(100,Math.round(score)));
  return {score,blocked:score<45,reasons:reasons.slice(0,6)};
}
