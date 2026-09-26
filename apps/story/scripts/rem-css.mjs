// Apply to imported/shared and editor styles only in Story's build.
// Leave percentages, viewport units, unitless values and media pixels in data alone.
export const toRem=value=>value.replace(/url\([^)]*\)|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(-?(?:\d*\.)?\d+)px\b/g,(match,n)=>n===undefined?match:`${Number((Number(n)/16).toFixed(6))}rem`);
export default function remCss(){
 return {postcssPlugin:'story-rem',Declaration(decl){decl.value=toRem(decl.value);},AtRule(rule){if(['media','container'].includes(rule.name))rule.params=toRem(rule.params);}};
}
