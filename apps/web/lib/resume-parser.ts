const SKILL_PATTERNS = [
  'TCP/IP','Routing','Switching','VLAN','VPN','Firewall','Cisco','CCNA','OSPF','BGP','EIGRP','DHCP','DNS','NAT','ACL',
  'Wireshark','Linux','Windows Server','Active Directory','SIEM','SOC','NOC','IDS/IPS','VAPT','Penetration Testing',
  'Cybersecurity','Information Security','Network Security','Incident Response','Digital Forensics','IAM','Zero Trust',
  'AWS','Azure','GCP','VPC','Cloud Networking','Cloud Security','Docker','Kubernetes','Python','Bash','PowerShell',
  'Git','GitHub','SQL','PostgreSQL','Supabase','REST API','Java','C','C++','JavaScript','TypeScript','Flutter',
];

const ROLE_PATTERNS = [
  'Network Engineer','Network Administrator','Network Support Engineer','NOC Engineer','SOC Analyst','Cybersecurity Analyst',
  'Security Analyst','Information Security Analyst','Network Security Engineer','Cloud Support Engineer','Cloud Network Engineer',
  'Cloud Engineer','Infrastructure Engineer','System Administrator','Security Operations Analyst','Technical Support Engineer',
];

const CERT_PATTERNS = ['CCNA','CCNP','CompTIA Security+','Security+','CEH','OSCP','AWS Certified','Azure Fundamentals','AZ-900','SC-900','Google Cybersecurity'];

const clean = (s:string)=>s.replace(/\s+/g,' ').trim();
const uniq = (v:string[])=>Array.from(new Set(v.map(clean).filter(Boolean)));

export async function extractResumeText(file:File){
  const buf = Buffer.from(await file.arrayBuffer());
  const mime = file.type;
  const name = file.name.toLowerCase();
  if(mime==='application/pdf' || name.endsWith('.pdf')){
    const pdfParse = (await import('pdf-parse')).default;
    const out = await pdfParse(buf);
    return clean(out.text || '');
  }
  if(mime==='application/vnd.openxmlformats-officedocument.wordprocessingml.document' || name.endsWith('.docx')){
    const mammoth = await import('mammoth');
    const out = await mammoth.extractRawText({buffer:buf});
    return clean(out.value || '');
  }
  if(mime==='text/plain' || name.endsWith('.txt')) return clean(buf.toString('utf8'));
  throw new Error('Unsupported resume format. Upload PDF, DOCX or TXT.');
}

function findKnown(text:string, values:string[]){
  const t=text.toLowerCase();
  return uniq(values.filter(x=>t.includes(x.toLowerCase())));
}

function inferName(text:string){
  const first = text.split(/\n|\r|\|/).map(clean).filter(Boolean).slice(0,5);
  return first.find(x=>/^[A-Za-z][A-Za-z .'-]{2,60}$/.test(x) && !/resume|curriculum|profile|engineer|developer/i.test(x)) || '';
}

export function parseResumeDeterministic(text:string){
  const email = text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)?.[0] || '';
  const phone = text.match(/(?:\+?91[-\s]?)?[6-9]\d{9}/)?.[0] || '';
  const linkedin = text.match(/https?:\/\/(?:www\.)?linkedin\.com\/[^\s)]+/i)?.[0] || '';
  const github = text.match(/https?:\/\/(?:www\.)?github\.com\/[^\s)]+/i)?.[0] || '';
  const skills = findKnown(text,SKILL_PATTERNS);
  const certifications = findKnown(text,CERT_PATTERNS);
  const roleMentions = findKnown(text,ROLE_PATTERNS);
  const degreeHits = uniq([
    ...(text.match(/\b(?:B\.?E\.?|B\.?Tech|Bachelor(?:'s)? of Engineering|Bachelor(?:'s)? of Technology)[^.;\n]{0,80}/ig)||[]),
    ...(text.match(/\b(?:M\.?E\.?|M\.?Tech|MCA|MSc)[^.;\n]{0,80}/ig)||[]),
  ]).slice(0,8);
  const explicitYears = [...text.matchAll(/(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)/ig)].map(m=>Number(m[1])).filter(Number.isFinite);
  const experienceYears = explicitYears.length ? Math.max(...explicitYears) : null;
  return {
    full_name: inferName(text), email, phone, linkedin_url:linkedin, github_url:github,
    skills, certifications, target_roles: roleMentions, education:degreeHits, experience_years:experienceYears,
  };
}

export async function enrichResumeWithGemini(text:string, base:any){
  const key=process.env.GEMINI_API_KEY;
  const model=process.env.GEMINI_MODEL || 'gemini-3.1-flash-lite';
  if(!key || !text) return base;
  const prompt=`Extract a job-search profile from this resume. Return ONLY JSON with keys full_name,email,phone,linkedin_url,github_url,skills,target_roles,certifications,education,experience_years. skills/target_roles/certifications/education must be arrays of short strings. Never invent facts. If absent, use empty string/array/null. Resume:\n${text.slice(0,18000)}`;
  try{
    const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`,{
      method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({contents:[{parts:[{text:prompt}]}],generationConfig:{responseMimeType:'application/json',temperature:0.1}})
    });
    if(!r.ok) return base;
    const j=await r.json();
    const raw=j?.candidates?.[0]?.content?.parts?.map((p:any)=>p.text||'').join('') || '';
    const ai=JSON.parse(raw);
    const mergeArray=(a:any,b:any)=>uniq([...(Array.isArray(a)?a:[]),...(Array.isArray(b)?b:[])]).slice(0,80);
    return {
      ...base,
      full_name: ai.full_name || base.full_name || '', email:ai.email || base.email || '', phone:ai.phone || base.phone || '',
      linkedin_url:ai.linkedin_url || base.linkedin_url || '', github_url:ai.github_url || base.github_url || '',
      skills:mergeArray(base.skills,ai.skills), target_roles:mergeArray(base.target_roles,ai.target_roles),
      certifications:mergeArray(base.certifications,ai.certifications), education:mergeArray(base.education,ai.education),
      experience_years: Number.isFinite(Number(ai.experience_years)) ? Number(ai.experience_years) : base.experience_years,
      ai_enriched:true,
    };
  }catch{return base;}
}
