/* Four-operation calculator: parsed data only, never JavaScript evaluation. */
(function(root){
 function calculate(source){
  const s=String(source).replaceAll(',','.').replaceAll('×','*').replaceAll('÷','/').replace(/\s/g,'');
  if(!s||s.length>64||!/^[0-9.+\-*/()]+$/.test(s))throw Error('Operación no válida.');
  const tokens=s.match(/(?:\d+(?:\.\d*)?|\.\d+)|[+\-*/()]/g)||[];
  if(tokens.join('')!==s)throw Error('Operación no válida.');
  let i=0;
  function atom(){const t=tokens[i++];if(t==='+'||t==='-')return(t==='-'?-1:1)*atom();if(t==='('){const n=sum();if(tokens[i++]!==')')throw Error('Falta cerrar el paréntesis.');return n}if(!t||!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(t))throw Error('Completa la operación.');return Number(t)}
  function product(){let n=atom();while(['*','/'].includes(tokens[i])){const op=tokens[i++],v=atom();if(op==='/'&&v===0)throw Error('No se puede dividir por cero.');n=op==='*'?n*v:n/v}return n}
  function sum(){let n=product();while(['+','-'].includes(tokens[i])){const op=tokens[i++],v=product();n=op==='+'?n+v:n-v}return n}
  const n=sum();if(i!==tokens.length||!Number.isFinite(n)||Math.abs(n)>1000000000)throw Error('Revisa el resultado.');return Number(n.toPrecision(12));
 }
 if(typeof module!=='undefined'&&module.exports)module.exports={calculate};else root.marchanCalculate=calculate;
})(typeof window!=='undefined'?window:this);
