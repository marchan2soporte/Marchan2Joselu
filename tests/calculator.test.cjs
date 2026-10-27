const test=require('node:test'),assert=require('node:assert/strict');
const {calculate}=require('../web/calculator.js');
test('decimal comma and currency-style arithmetic',()=>{assert.equal(calculate('0,1+0,2'),.3);assert.equal(calculate('20-3,50'),16.5)});
test('precedence, parentheses and unary values',()=>{assert.equal(calculate('2+3*4'),14);assert.equal(calculate('(2+3)×4'),20);assert.equal(calculate('-2+3'),1);assert.equal(calculate('12÷3'),4)});
test('reject incomplete and non-finite operations',()=>{for(const x of ['','1+','1/0','NaN','3..4','(1+2','2(3)'])assert.throws(()=>calculate(x))});
test('reject code injection and oversized input',()=>{for(const x of ['process.exit()','1;alert(1)','2**3','1'.repeat(70)])assert.throws(()=>calculate(x))});
