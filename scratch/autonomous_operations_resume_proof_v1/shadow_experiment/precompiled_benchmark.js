
const regex = /[\p{L}\p{N}\s]/gu;
const text = "Test phrase with international text";
console.log(regex.test(text));
