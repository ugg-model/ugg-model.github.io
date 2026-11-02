// A conceptual overview of conditional queries, separate from gallery state.
const tasks = [
  {id:"reconstruction",label:"3D Reconstruction",inputs:["rgb"],outputs:["depth","camera"],
    detail:"Observed RGB → depth and camera geometry → a colored 3D scene.",rgb:"Full RGB sequence"},
  {id:"nvs",label:"Novel View Synthesis",inputs:["rgb","camera"],outputs:["rgb"],
    detail:"Two RGB conditioning frames and target cameras → novel-view RGB.",
    rgb:"2 conditioning frames",camera:"Target camera poses"},
  {id:"depth",label:"Depth Prediction",inputs:["rgb"],outputs:["depth"],
    detail:"Observed RGB → a depth sequence aligned with the video.",rgb:"Full RGB sequence"},
  {id:"camera",label:"Camera Prediction",inputs:["rgb"],outputs:["camera"],
    detail:"Observed RGB → camera positions and orientations through time.",rgb:"Full RGB sequence"},
  {id:"depth-to-video",label:"Depth-to-Video",inputs:["depth"],outputs:["rgb"],section:false,
    detail:"A depth sequence → the RGB appearance that fits that geometry.",
    rgb:"Not conditioned",depth:"Observed geometry"},
  {id:"camera-to-video",label:"Camera-to-Video",inputs:["camera"],outputs:["rgb"],section:false,
    detail:"A camera trajectory → an RGB video that follows it.",
    rgb:"Not conditioned",camera:"Observed trajectory"},
  {id:"generation",label:"Text-to-4D",inputs:["text"],outputs:["rgb","depth","camera"],
    detail:"A text description → RGB, depth, and camera motion.",rgb:"Observed appearance"},
];
const colors={text:"#8a67ad",rgb:"#4a73b6",depth:"#258d86",camera:"#b98035"};
const root=document.querySelector("#results-flow");
const filmstrip = kind => '<div class="flow-filmstrip" aria-hidden="true">'+
  [0,1,2].map(index=>'<span class="flow-frame flow-'+kind+'-frame frame-'+index+'"></span>').join("")+"</div>";
const cameraArt = '<svg class="flow-camera-art" viewBox="0 0 180 42" aria-hidden="true">'+
  '<path class="flow-grid" d="M8 35H170M22 21H156M37 8H144M26 40L54 3M67 40L80 3M109 40L106 3M153 40L132 3"/>'+
  '<path class="flow-trajectory" d="M30 31C52 29 51 14 80 19S116 29 153 10"/>'+
  '<path class="flow-frusta" d="M28 31L41 22L44 35ZM80 19L94 11L96 25ZM148 13L161 4L167 18Z"/>'+
  "</svg>";
function node(side,key,title,subtitle,art){
  return '<div class="flow-node" data-side="'+side+'" data-modality="'+key+'" style="--node-color:'+colors[key]+'">'+
    '<div class="flow-node-top"><span class="flow-node-dot"></span><strong>'+title+'</strong><span class="flow-state">Available</span></div>'+
    art+'<span class="flow-node-detail">'+subtitle+"</span></div>";
}
root.innerHTML='<div class="flow-task-picker" role="group" aria-label="Choose a model task">'+
  tasks.map(t=>'<button type="button" id="flow-task-'+t.id+'" data-task="'+t.id+'" aria-pressed="false">'+t.label+"</button>").join("")+
  '</div><div class="flow-board" data-visible="false" role="group" aria-label="Inputs flow through UGG to generated outputs">'+
  '<svg class="flow-wires" aria-hidden="true"><defs><marker id="flow-arrow-muted" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#c8cdd6"/></marker>'+
  Object.entries(colors).map(([key,color])=>'<marker id="flow-arrow-'+key+'" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="'+color+'"/></marker>').join("")+
  '</defs><g class="flow-routes"></g><path class="flow-mobile-route" data-direction="input" marker-end="url(#flow-arrow-muted)"/><path class="flow-mobile-route" data-direction="output" marker-end="url(#flow-arrow-muted)"/></svg>'+
  '<div class="flow-inputs"><p class="flow-column-heading">INPUT CONDITIONING</p>'+
  node("input","text","Text","A scene description",'<div class="flow-prompt" aria-hidden="true">“Describe a scene…”</div>')+
  node("input","rgb","RGB frames","Observed appearance",filmstrip("rgb"))+
  node("input","depth","Depth","Optional conditioning",filmstrip("depth"))+
  node("input","camera","Camera","Supplied geometry",cameraArt)+
  '</div><div class="flow-model"><span class="flow-model-eyebrow">ONE JOINT MODEL</span><span class="flow-model-mark">UGG</span>'+
  '<strong>Unified Generative<br>Geometry</strong><div class="flow-model-rule"></div><p>Complete the scene<br>from what is observed.</p>'+
  '<div class="flow-model-tokens"><span>RGB</span><span>Depth</span><span>Camera</span></div></div>'+
  '<div class="flow-outputs"><p class="flow-column-heading">GENERATED OUTPUTS</p>'+
  node("output","rgb","RGB video","Appearance through time",filmstrip("rgb"))+
  node("output","depth","Depth sequence","Scene structure",filmstrip("depth"))+
  node("output","camera","Camera trajectory","Positions & orientations",cameraArt)+
  '</div></div><div class="flow-footer"><p class="flow-summary" aria-live="polite">Choose a task to trace its path through UGG.</p>'+
  '<a class="flow-explore" href="#reconstruction" hidden>Explore examples <span aria-hidden="true">↓</span></a></div>';
root.hidden=false;
const board=root.querySelector(".flow-board"),model=root.querySelector(".flow-model"),routes=root.querySelector(".flow-routes");
const nodes=[...root.querySelectorAll(".flow-node")],buttons=[...root.querySelectorAll(".flow-task-picker button")],paths=new Map();
let inView=false;
for(const item of nodes){
  const path=document.createElementNS("http://www.w3.org/2000/svg","path");
  path.classList.add("flow-route");path.dataset.side=item.dataset.side;path.dataset.modality=item.dataset.modality;
  path.style.setProperty("--route-color",colors[item.dataset.modality]);path.setAttribute("marker-end","url(#flow-arrow-muted)");
  routes.append(path);paths.set(item,path);
}
function drawWires(){
  const b=board.getBoundingClientRect(),m=model.getBoundingClientRect(),svg=root.querySelector(".flow-wires");
  if(!b.width||!b.height)return;
  svg.setAttribute("viewBox","0 0 "+b.width+" "+b.height);
  const vertical=matchMedia("(max-width: 680px)").matches;
  for(const path of root.querySelectorAll(".flow-mobile-route")){
    const input=path.dataset.direction==="input";
    const source=(input?root.querySelector(".flow-inputs"):model).getBoundingClientRect();
    const target=(input?model:root.querySelector(".flow-outputs")).getBoundingClientRect();
    const x=b.width/2,y1=source.bottom-b.top+4,y2=target.top-b.top-6;
    path.setAttribute("d","M"+x+","+y1+" L"+x+","+y2);
  }
  for(const node of nodes){
    const r=node.getBoundingClientRect(),input=node.dataset.side==="input";
    const siblings=nodes.filter(n=>n.dataset.side===node.dataset.side),index=siblings.indexOf(node);
    const offset=(index-(siblings.length-1)/2)*12;
    let d;
    if(vertical){
      const startX=(input?r.left+r.width/2:m.left+m.width/2+offset)-b.left;
      const endX=(input?m.left+m.width/2+offset:r.left+r.width/2)-b.left;
      const startY=(input?r.bottom+3:m.bottom+3)-b.top,endY=(input?m.top-5:r.top-5)-b.top;
      d="M"+startX+","+startY+" C"+startX+","+(startY+24)+" "+endX+","+(endY-24)+" "+endX+","+endY;
    }else{
      const startX=(input?r.right+4:m.right+4)-b.left,endX=(input?m.left-6:r.left-6)-b.left;
      const startY=(input?r.top+r.height/2:m.top+m.height/2+offset)-b.top;
      const endY=(input?m.top+m.height/2+offset:r.top+r.height/2)-b.top;
      d="M"+startX+","+startY+" C"+(startX+28)+","+startY+" "+(endX-28)+","+endY+" "+endX+","+endY;
    }
    paths.get(node).setAttribute("d",d);
  }
}
function choose(task){
  board.dataset.task=task.id;model.classList.add("has-selection");
  root.querySelectorAll(".flow-mobile-route").forEach(path=>{path.dataset.active="true";path.setAttribute("marker-end","url(#flow-arrow-rgb)");});
  buttons.forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.task===task.id)));
  for(const node of nodes){
    const active=(node.dataset.side==="input"?task.inputs:task.outputs).includes(node.dataset.modality);
    node.classList.toggle("is-active",active);
    node.querySelector(".flow-state").textContent=active?(node.dataset.side==="input"?"Observed":"Generated"):"Available";
    const path=paths.get(node);path.dataset.active=String(active);
    path.setAttribute("marker-end","url(#flow-arrow-"+(active?node.dataset.modality:"muted")+")");
  }
  root.querySelector('[data-side="input"][data-modality="rgb"] .flow-node-detail').textContent=task.rgb;
  root.querySelector('[data-side="input"][data-modality="depth"] .flow-node-detail').textContent=task.depth||"Optional conditioning";
  root.querySelector('[data-side="input"][data-modality="camera"] .flow-node-detail').textContent=task.camera||"Supplied geometry";
  root.querySelector(".flow-summary").textContent=task.detail;
  const explore=root.querySelector(".flow-explore"),hasSection=task.section!==false;
  explore.hidden=!hasSection;
  if(hasSection){explore.href="#"+task.id;explore.setAttribute("aria-label","Explore "+task.label+" examples");}
  drawWires();
}
const picker=root.querySelector(".flow-task-picker"),summary=root.querySelector(".flow-summary");
const CYCLE_MS=2500,stillness=matchMedia("(prefers-reduced-motion: reduce)");
let cycle=null,cycleIndex=0,autoplay=!stillness.matches,paused=false;
function syncCycle(){
  const running=autoplay&&!paused&&inView&&!document.hidden;
  if(running&&!cycle)cycle=setInterval(()=>{cycleIndex=(cycleIndex+1)%tasks.length;choose(tasks[cycleIndex]);},CYCLE_MS);
  else if(!running&&cycle){clearInterval(cycle);cycle=null;}
  picker.dataset.cycling=String(running);
}
// A reader who reaches for the picker owns it from then on; the summary only starts
// announcing once it stops changing on its own.
function takeOver(index){autoplay=false;paused=false;cycleIndex=index;summary.setAttribute("aria-live","polite");syncCycle();}
for(const event of ["pointerenter","focusin"])picker.addEventListener(event,()=>{paused=true;syncCycle();});
for(const event of ["pointerleave","focusout"])picker.addEventListener(event,()=>{paused=false;syncCycle();});
stillness.addEventListener("change",()=>{if(stillness.matches){autoplay=false;summary.setAttribute("aria-live","polite");syncCycle();}});
buttons.forEach((button,index)=>{
  button.addEventListener("click",()=>{takeOver(index);choose(tasks[index]);});
  button.addEventListener("keydown",event=>{
    let target;
    if(event.key==="ArrowRight")target=(index+1)%buttons.length;
    if(event.key==="ArrowLeft")target=(index+buttons.length-1)%buttons.length;
    if(event.key==="Home")target=0;
    if(event.key==="End")target=buttons.length-1;
    if(target!==undefined){event.preventDefault();buttons[target].focus();buttons[target].click();}
  });
});
new ResizeObserver(drawWires).observe(board);
document.fonts.ready.then(drawWires);
function motionVisibility(){board.dataset.visible=String(inView&&!document.hidden);syncCycle();}
new IntersectionObserver(entries=>{inView=entries.at(-1).isIntersecting;motionVisibility();}).observe(board);
document.addEventListener("visibilitychange",motionVisibility);
summary.setAttribute("aria-live",autoplay?"off":"polite");
choose(tasks[cycleIndex]);
syncCycle();
drawWires();
