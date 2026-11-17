import {useState,useEffect,useCallback} from 'react'
const API=(import.meta.env.VITE_API_URL||'https://quiz-api-967410411564.asia-south1.run.app').replace(/\/$/,'')
let token=localStorage.getItem('t')||''
async function api(path,opt={}){
  const r=await fetch(API+path,{...opt,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:opt.body?JSON.stringify(opt.body):undefined})
  const d=r.status===204?null:await r.json().catch(()=>null)
  if(!r.ok)throw new Error(d?.errors?.map(e=>e.field+': '+e.message).join(', ')||d?.detail||'Something went wrong. Try again.')
  return d
}
const Chip=({n,label,tone='gold'})=><div className={'chip '+tone}><b>{n}</b><span>{label}</span></div>

function Auth({onDone,flash,toast}){
  const [show,setShow]=useState(false),[reg,setReg]=useState(false),[f,setF]=useState({email:'',full_name:'',password:''}),[busy,setBusy]=useState(false)
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async e=>{e.preventDefault();setBusy(true)
    try{if(reg)await api('/auth/register',{method:'POST',body:f})
      const d=await api('/auth/login',{method:'POST',body:{email:f.email,password:f.password}})
      token=d.access_token;localStorage.setItem('t',token);onDone()}
    catch(x){flash(x.message)}setBusy(false)}
  return <div className="auth"><div className="hero">
    <h1>Put credits on your knowledge.</h1>
    <p>Stake credits to enter a quiz. Pass and win the reward. Miss and the stake stays on the table.</p>
    <div className="stack"><Chip n="500" label="free credits to start"/><Chip n="x2" label="typical reward" tone="red"/></div></div>
    <form className="card" onSubmit={go}><h2>{reg?'Create your account':'Welcome back'}</h2>
      <input placeholder="Email" type="email" value={f.email} onChange={set('email')} required/>
      {reg&&<input placeholder="Full name" value={f.full_name} onChange={set('full_name')} required/>}
      <div className="pw"><input placeholder="Password (8+ characters)" type={show?'text':'password'} value={f.password} onChange={set('password')} required/><button type="button" className="eye" aria-label={show?'Hide password':'Show password'} onClick={()=>setShow(!show)}>{show?<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.9 17.9A10.9 10.9 0 0 1 12 19C5 19 1 12 1 12a18.5 18.5 0 0 1 5.1-5.9M9.9 4.2A9.1 9.1 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.2 3.2M1 1l22 22"/></svg>:<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>}</button></div>
      <button className="btn" disabled={busy}>{busy?'Working...':reg?'Create account and get 500 credits':'Log in'}</button>
      <button type="button" className="link" onClick={()=>setReg(!reg)}>{reg?'I already have an account':'New here? Create an account'}</button></form>
    {toast&&<div className="toast">{toast}</div>}</div>
}

function Home({user,flash,begin}){
  const [qs,setQs]=useState(null)
  const load=()=>api('/quizzes').then(setQs).catch(e=>flash(e.message));useEffect(()=>{load()},[]);const [ask,setAsk]=useState(null);const confirmAsk=async()=>{const {q,step}=ask;try{if(step==='hide'){await api(`/admin/quizzes/${q.id}`,{method:'PATCH',body:{is_active:false}});flash('Quiz hidden from players')}else{await api(`/admin/quizzes/${q.id}`,{method:'DELETE'});flash('Quiz deleted')}setAsk(null)}catch(e){if(step==='delete'&&/attempts/.test(e.message)){setAsk({q,step:'hide'});return}flash(e.message);setAsk(null)}load()};const remove=async q=>{if(!window.confirm(`Delete "${q.title}"? This cannot be undone.`))return;try{await api(`/admin/quizzes/${q.id}`,{method:'DELETE'});flash('Quiz deleted')}catch(e){if(/attempts/.test(e.message)&&window.confirm('This quiz already has attempts, so it cannot be deleted. Hide it from players instead?')){try{await api(`/admin/quizzes/${q.id}`,{method:'PATCH',body:{is_active:false}});flash('Quiz hidden from players')}catch(x){flash(x.message)}}else flash(e.message)}load()}
  const enter=async q=>{try{const a=await api(`/quizzes/${q.id}/start`,{method:'POST'});begin(q,a)}catch(e){const m=/id=(\d+)/.exec(e.message);if(!m)return flash(e.message);try{const d=await api(`/quizzes/${q.id}`);begin(q,{attempt_id:Number(m[1]),staked_amount:q.stake_amount,questions:d.questions});flash('Resuming your open attempt')}catch(x){flash(x.message)}}}
  if(!qs)return <p className="muted">Shuffling the deck...</p>
  if(!qs.length)return <p className="muted">No quizzes yet. Ask an admin to add one.</p>
  return <><div className="grid">{qs.map(q=><article className="card quiz" key={q.id}>
    <Chip n={q.stake_amount} label="to enter"/>
    <div><h3>{q.title}</h3><p className="muted">{q.description||'Answer well and the table pays out.'}</p>
    <p className="meta">{q.question_count} questions. Pass at {q.pass_percentage}%. Win {q.reward_amount} credits.</p></div>
    <button className="btn" disabled={user.credits<q.stake_amount} onClick={()=>enter(q)}>{user.credits<q.stake_amount?'Not enough credits':`Stake ${q.stake_amount} and play`}</button>{user.role==='admin'&&<button className="del" aria-label="Delete quiz" title="Delete quiz" onClick={()=>setAsk({q,step:'delete'})}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg></button>}</article>)}</div>{ask&&<div className="veil" onClick={()=>setAsk(null)}><div className="card dialog" onClick={e=>e.stopPropagation()}><h3>{ask.step==='hide'?'Hide this quiz instead?':'Delete this quiz?'}</h3><p className="muted">{ask.step==='hide'?`"${ask.q.title}" already has attempts, so it can't be deleted. Hide it from players and keep the history?`:`"${ask.q.title}" will be removed for good. This can't be undone.`}</p><div className="acts"><button className="btn ghost" onClick={()=>setAsk(null)}>Keep it</button><button className="btn danger" onClick={confirmAsk}>{ask.step==='hide'?'Hide quiz':'Delete quiz'}</button></div></div></div>}</>
}

function Play({run,done,flash}){
  const {a}=run,qs=a.questions,[i,setI]=useState(0),[ans,setAns]=useState([]),[busy,setBusy]=useState(false)
  const pick=async o=>{const next=[...ans,{question_id:qs[i].id,selected_option:o}]
    if(i<qs.length-1){setAns(next);setI(i+1);return}
    setBusy(true)
    try{done(await api(`/attempts/${a.attempt_id}/submit`,{method:'POST',body:{answers:next}}))}catch(e){flash(e.message);setBusy(false)}}
  const q=qs[i]
  return <div className="card play"><div className="bar"><i style={{width:(i/qs.length*100)+'%'}}/></div>
    <p className="muted">Question {i+1} of {qs.length}. {a.staked_amount} credits on the table.</p>
    <h2>{q.text}</h2><div className="opts">{q.options.map((o,k)=><button key={k} disabled={busy} onClick={()=>pick(k)}><b>{'ABCDEF'[k]}</b>{o}</button>)}</div></div>
}

function Result({r,again}){
  return <div className={'card result '+(r.passed?'win':'lose')}>
    <div className="ring" style={{'--p':r.percentage}}><b>{r.score}/{r.total_questions}</b></div>
    <h2>{r.passed?`You won ${r.reward_amount} credits`:`The stake stays on the table`}</h2>
    <p className="muted">{r.percentage}% scored, {r.pass_percentage}% needed. Your balance is now {r.balance} credits.</p>
    <button className="btn" onClick={again}>Back to quizzes</button></div>
}

function Wallet({user,refresh,flash}){
  const [tx,setTx]=useState([]),[decline,setDecline]=useState(false)
  const load=()=>api('/credits/transactions?limit=50').then(setTx).catch(e=>flash(e.message))
  useEffect(()=>{load()},[])
  const buy=async n=>{try{await api('/credits/purchase',{method:'POST',body:{amount:n,payment_method:decline?'mock_card_decline':'mock_card_success'}});flash(`Added ${n} credits`);refresh();load()}catch(e){flash(e.message)}}
  return <div className="two"><div className="card"><h2>Buy credits</h2><p className="muted">Payments are simulated. No real money moves.</p>
    <div className="buy">{[100,500,1000].map(n=><button key={n} className="chipbtn" onClick={()=>buy(n)}><b>{n}</b>credits</button>)}</div>
    <label className="check"><input type="checkbox" checked={decline} onChange={e=>setDecline(e.target.checked)}/>Simulate a declined card</label></div>
    <div className="card"><h2>Ledger</h2><ul className="ledger">{tx.map(t=><li key={t.id}><span>{t.description||t.type}<small>{new Date(t.created_at).toLocaleString()}</small></span>
      <b className={t.amount<0?'neg':'pos'}>{t.amount>0?'+':''}{t.amount}<small>{t.balance_after} left</small></b></li>)}</ul></div></div>
}

function Admin({flash,done}){
  const [f,setF]=useState({title:'',description:'',stake_amount:100,reward_amount:200,pass_percentage:60,lines:'Which keyword defines a function? | func | def | lambda | 2\nWhich type is immutable? | list | dict | tuple | 3'})
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const save=async e=>{e.preventDefault()
    try{const questions=f.lines.split('\n').filter(Boolean).map(l=>{const p=l.split('|').map(s=>s.trim());return{text:p[0],options:p.slice(1,-1),correct_option:Number(p[p.length-1])-1}})
      await api('/admin/quizzes',{method:'POST',body:{title:f.title,description:f.description||null,stake_amount:+f.stake_amount,reward_amount:+f.reward_amount,pass_percentage:+f.pass_percentage,questions}})
      flash('Quiz published');done()}catch(x){flash(x.message)}}
  return <form className="card admin" onSubmit={save}><h2>Publish a quiz</h2>
    <input placeholder="Title" value={f.title} onChange={set('title')} required/><input placeholder="Description" value={f.description} onChange={set('description')}/>
    <div className="row"><label>Stake<input type="number" value={f.stake_amount} onChange={set('stake_amount')}/></label><label>Reward<input type="number" value={f.reward_amount} onChange={set('reward_amount')}/></label><label>Pass %<input type="number" value={f.pass_percentage} onChange={set('pass_percentage')}/></label></div>
    <label>One question per line: question | option | option | number of the correct option<textarea rows="5" value={f.lines} onChange={set('lines')}/></label>
    <button className="btn">Publish quiz</button></form>
}

export default function App(){
  const [user,setUser]=useState(null),[view,setView]=useState('home'),[run,setRun]=useState(null),[res,setRes]=useState(null),[toast,setToast]=useState('')
  const flash=m=>{setToast(m);setTimeout(()=>setToast(''),4000)}
  const refresh=useCallback(()=>api('/auth/me').then(setUser).catch(()=>{token='';localStorage.removeItem('t');setUser(null)}),[])
  useEffect(()=>{token&&refresh()},[refresh])
  const out=()=>{token='';localStorage.removeItem('t');setUser(null);setView('home')}
  if(!user)return <Auth onDone={refresh} flash={flash} toast={toast}/>
  const tabs=[['home','Quizzes'],['wallet','Wallet'],...(user.role==='admin'?[['admin','Admin']]:[])]
  return <div className="app"><header><h1 className="logo">Quiz Arena</h1>
    <nav>{tabs.map(([k,l])=><button key={k} className={view===k?'on':''} onClick={()=>setView(k)}>{l}</button>)}</nav>
    <div className="bank"><Chip n={user.credits} label="credits" tone="red"/><button className="link" onClick={out}>Log out</button></div></header>
    <main>{view!=='home'&&<button className="back" onClick={()=>setView('home')}>Back to quizzes</button>}{view==='home'&&<><h2 className="title">Pick a table, {user.full_name.split(' ')[0]}.</h2><Home user={user} flash={flash} begin={(q,a)=>{setRun({q,a});setView('play');refresh()}}/></>}
    {view==='play'&&run&&<Play run={run} flash={flash} done={r=>{setRes(r);setView('result');refresh()}}/>}
    {view==='result'&&res&&<Result r={res} again={()=>setView('home')}/>}
    {view==='wallet'&&<Wallet user={user} refresh={refresh} flash={flash}/>}
    {view==='admin'&&<Admin flash={flash} done={()=>setView('home')}/>}</main>{toast&&<div className="toast">{toast}</div>}</div>
}