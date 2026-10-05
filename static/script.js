const q = window.questions;
if(q){
let index=0,total=0;
const question=document.getElementById("question"),answer=document.getElementById("answer");
const submit=document.getElementById("submit"),next=document.getElementById("next");
const feedback=document.getElementById("feedback"),learningAnswer=document.getElementById("learningAnswer"),counter=document.getElementById("counter"),bar=document.getElementById("bar");
function show(){question.textContent=q[index].question;answer.value="";feedback.classList.add("hidden");learningAnswer.classList.add("hidden");next.classList.add("hidden");submit.classList.remove("hidden");counter.textContent=`Question ${index+1} / ${q.length}`;bar.style.width=((index+1)/q.length*100)+"%"}
show();
submit.onclick=async()=>{
 if(!answer.value.trim()){alert("Please enter an answer.");return}
 submit.disabled=true;
 try{
 const r=await fetch("/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({index,answer:answer.value})});
 const data=await r.json();
 if(!r.ok) throw new Error(data.error||"Evaluation failed");
 total+=Number(data.score);
 feedback.innerHTML=`<strong>Score: ${data.score}/10</strong><br><br>${data.feedback}`;
 feedback.classList.remove("hidden");
 learningAnswer.innerHTML=`<b>Recommended Answer / Key Points:</b><span>${data.ideal_answer || "Review the key concepts mentioned in the feedback and try answering again."}</span>`;
 learningAnswer.classList.remove("hidden");
 submit.classList.add("hidden");
 if(index<q.length-1) next.classList.remove("hidden");
 else {next.textContent="Finish Interview →";next.classList.remove("hidden")}
 }catch(e){alert(e.message)} finally{submit.disabled=false}
};
next.onclick=()=>{index++;if(index<q.length) show();else{document.getElementById("finalScore").value=(total/q.length).toFixed(1);document.getElementById("finish").submit()}};
}

const stars=document.querySelectorAll('.star');
const feedbackBox=document.getElementById('appFeedback');
const sendFeedback=document.getElementById('sendFeedback');
const feedbackMessage=document.getElementById('feedbackMessage');
let selectedRating=0;
if(stars.length){
  stars.forEach(star=>star.addEventListener('click',()=>{
    selectedRating=Number(star.dataset.rating);
    stars.forEach(s=>s.classList.toggle('selected',Number(s.dataset.rating)<=selectedRating));
  }));
}
if(sendFeedback){
  sendFeedback.addEventListener('click',async()=>{
    if(!selectedRating){feedbackMessage.textContent='Please select a rating.';feedbackMessage.classList.remove('hidden');return;}
    if(!feedbackBox.value.trim()){feedbackMessage.textContent='Please enter your feedback.';feedbackMessage.classList.remove('hidden');return;}
    sendFeedback.disabled=true;
    try{
      const r=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rating:selectedRating,comments:feedbackBox.value})});
      const data=await r.json();
      feedbackMessage.textContent=data.message||data.error||'Feedback submitted.';
      feedbackMessage.classList.remove('hidden');
      if(r.ok){sendFeedback.textContent='Feedback Submitted ✓';feedbackBox.disabled=true;stars.forEach(s=>s.disabled=true)}
    }catch(e){feedbackMessage.textContent='Could not submit feedback. Please try again.';feedbackMessage.classList.remove('hidden')}
    finally{sendFeedback.disabled=false}
  });
}

// GenAI Study Assistant chat
const chatToggle=document.getElementById('chatToggle');
const chatPanel=document.getElementById('ai-chat');
const chatClose=document.getElementById('chatClose');
const chatForm=document.getElementById('chatForm');
const chatInput=document.getElementById('chatInput');
const chatMessages=document.getElementById('chatMessages');
const chatSend=document.getElementById('chatSend');
const chatStatus=document.getElementById('chatStatus');

function addChatMessage(text, type){
  const div=document.createElement('div');
  div.className=`chat-bubble ${type}`;
  if(type==='bot'){
    const b=document.createElement('b'); b.textContent='InterviewAI: '; div.appendChild(b);
    div.appendChild(document.createTextNode(text));
  }else div.textContent=text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop=chatMessages.scrollHeight;
  return div;
}

function currentChatContext(){
  const ctx={};
  if(window.questions && window.questions.length){
    ctx.interview_type=document.querySelector('.interview-head p')?.textContent || '';
    ctx.current_question=document.getElementById('question')?.textContent || '';
  }
  return ctx;
}

if(chatToggle && chatPanel){
  const openChat=()=>{chatPanel.classList.remove('hidden');chatInput?.focus();};
  chatToggle.addEventListener('click',openChat);
  chatClose?.addEventListener('click',()=>chatPanel.classList.add('hidden'));
  document.querySelectorAll('.chat-nav-link').forEach(a=>a.addEventListener('click',(e)=>{e.preventDefault();openChat();}));
}

if(chatForm){
  chatForm.addEventListener('submit',async(e)=>{
    e.preventDefault();
    const message=chatInput.value.trim();
    if(!message)return;
    addChatMessage(message,'user');
    chatInput.value=''; chatInput.disabled=true; chatSend.disabled=true;
    chatStatus.textContent='AI is thinking...';
    const previous=[...chatMessages.querySelectorAll('.chat-bubble')].slice(-8).map(el=>({
      role:el.classList.contains('user')?'user':'assistant', content:el.textContent
    }));
    try{
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:previous,context:currentChatContext()})});
      const data=await r.json();
      if(!r.ok) throw new Error(data.error||'AI chat is unavailable.');
      addChatMessage(data.answer||'No answer returned.','bot');
      chatStatus.textContent=data.offline?'Offline assistant: predefined interview knowledge base.':'';
    }catch(err){
      addChatMessage(err.message,'bot');
      chatStatus.textContent='';
    }finally{chatInput.disabled=false;chatSend.disabled=false;chatInput.focus();}
  });
}
