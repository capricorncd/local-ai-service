import {Children, isValidElement, useEffect, useId, useLayoutEffect, useRef, useState} from 'react';
import type {ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {ChevronDown} from 'lucide-react';
import './Autocomplete.css';

type Option = {value: string; label: string; disabled?: boolean};
type Props = {
 id?: string; label?: string; value: string; options: readonly (string | Option)[];
 onChange: (value: string) => void; placeholder?: string; disabled?: boolean;
 allowCustom?: boolean; className?: string;
};

export function Autocomplete({id, label, value, options, onChange, placeholder, disabled = false, allowCustom = true, className = ''}: Props) {
 const uid = useId(), inputId = id || uid, listId = uid + '-suggestions';
 const input = useRef<HTMLInputElement>(null), popup = useRef<HTMLDivElement>(null), root = useRef<HTMLDivElement>(null);
 const [open, setOpen] = useState(false), [query, setQuery] = useState<string | null>(null), [active, setActive] = useState(-1);
 const [position, setPosition] = useState({left: 0, top: 0, width: 0, maxHeight: 240});
 const normalized = options.map(option => typeof option === 'string' ? {value: option, label: option} : option);
 const unique = normalized.filter((option, index) => normalized.findIndex(item => item.value === option.value) === index);
 const display = allowCustom ? value : unique.find(option => option.value === value)?.label ?? value;
 const choices = unique.filter(option => query === null || (option.label + ' ' + option.value).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
 const visible = open && !disabled;
 const lang = typeof document === 'undefined' ? 'zh' : document.documentElement.lang;
 const en = lang.startsWith('en'), ja = lang.startsWith('ja');
 const suggestions = en ? 'Suggestions' : ja ? '候補' : '建议';
 const empty = allowCustom ? (en ? 'No suggestions. Enter your own value.' : ja ? '候補なし。直接入力できます。' : '无匹配预设，可直接输入') : (en ? 'No matching options' : ja ? '該当する候補がありません' : '无匹配选项');
 const close = () => {setOpen(false); setQuery(null); setActive(-1);};
 const show = () => {setQuery(null); setActive(-1); setOpen(true);};
 const choose = (choice: Option) => {if (choice.disabled) return; if (choice.value !== value) onChange(choice.value); close();};
 // Searching fixed choices never writes partial or invalid configuration values.
 useEffect(() => {if (!allowCustom || disabled) {setQuery(null); setActive(-1);}}, [value, disabled, allowCustom]);
 useLayoutEffect(() => {
  if (!visible) return;
  const place = () => {
   const rect = input.current!.getBoundingClientRect();
   const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
   const gap = .25 * rem, margin = .5 * rem;
   const desired = Math.min(15 * rem, Math.max(1, choices.length) * 2.5 * rem + .5 * rem);
   const below = window.innerHeight - rect.bottom - margin, above = rect.top - margin;
   const bottom = below >= desired || below >= above;
   const maxHeight = Math.max(0, Math.min(desired, bottom ? below : above) - gap);
   const width = Math.min(rect.width, window.innerWidth - margin * 2);
   setPosition({left: Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin)), top: bottom ? rect.bottom + gap : Math.max(margin, rect.top - maxHeight - gap), width, maxHeight});
  };
  place(); window.addEventListener('resize', place); window.addEventListener('scroll', place, true);
  return () => {window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true);};
 }, [visible, choices.length]);
 useEffect(() => {
  if (!visible) return;
  const outside = (event: PointerEvent) => {if (!root.current?.contains(event.target as Node) && !popup.current?.contains(event.target as Node)) close();};
  document.addEventListener('pointerdown', outside);
  return () => document.removeEventListener('pointerdown', outside);
 }, [visible]);
 useEffect(() => {popup.current?.querySelector<HTMLElement>('[data-active=true]')?.scrollIntoView?.({block: 'nearest'});}, [active]);
 return <div className={'ui-autocomplete ' + className} ref={root}>
  <input ref={input} id={inputId} role="combobox" aria-label={label} aria-autocomplete="list" aria-expanded={visible} aria-controls={visible ? listId : undefined} aria-activedescendant={visible && active >= 0 && choices[active] ? listId + '-' + active : undefined} autoComplete="off" disabled={disabled} value={!allowCustom && query !== null ? query : display} placeholder={placeholder}
   onFocus={show} onClick={() => {if (!visible) show();}} onBlur={close}
   onChange={event => {if (allowCustom) onChange(event.target.value); setQuery(event.target.value); setActive(-1); setOpen(true);}}
   onKeyDown={event => {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
     event.preventDefault();
     if (!visible) {show(); return;}
     const enabled = choices.map((option, index) => option.disabled ? -1 : index).filter(index => index >= 0);
     if (enabled.length) {const current = enabled.indexOf(active); setActive(enabled[current < 0 ? (event.key === 'ArrowDown' ? 0 : enabled.length - 1) : (current + (event.key === 'ArrowDown' ? 1 : -1) + enabled.length) % enabled.length]);}
    } else if (event.key === 'Enter' && visible) {
     event.preventDefault();
     const choice = choices[active] ?? (!allowCustom && query !== null ? choices.find(option => !option.disabled && (option.label === query || option.value === query)) : undefined);
     if (choice) choose(choice); else close();
    } else if (event.key === 'Escape' && visible) {event.preventDefault(); event.stopPropagation(); close();}
   }}/>
  <button type="button" tabIndex={-1} className="ui-autocomplete-toggle" aria-label={[label, suggestions].filter(Boolean).join(' ')} disabled={disabled} onMouseDown={event => event.preventDefault()} onClick={() => {if (visible) close(); else {input.current?.focus(); show();}}}><ChevronDown size="1rem"/></button>
  {visible && createPortal(<div ref={popup} id={listId} role="listbox" aria-label={[label, suggestions].filter(Boolean).join(' ')} className="ui-autocomplete-menu" style={position} onMouseDown={event => event.preventDefault()}>
   {choices.length ? choices.map((choice, index) => <div key={choice.value} id={listId + '-' + index} role="option" aria-selected={choice.value === value} aria-disabled={choice.disabled || undefined} data-active={active === index} className="ui-autocomplete-option" onMouseEnter={() => setActive(choice.disabled ? -1 : index)} onClick={event => {event.preventDefault(); choose(choice);}}>{choice.label}</div>) : <div className="ui-autocomplete-empty">{empty}</div>}
  </div>, input.current?.closest('dialog') || document.body)}
 </div>;
}

function textContent(node: ReactNode): string {
 return Children.toArray(node).map(child => isValidElement<{children?: ReactNode}>(child) ? textContent(child.props.children) : String(child)).join('');
}
function readOptions(children: ReactNode): Option[] {
 return Children.toArray(children).flatMap(child => {
  if (!isValidElement<{value?: string | number; children?: ReactNode; disabled?: boolean}>(child)) return [];
  if (child.type !== 'option') return readOptions(child.props.children);
  const label = textContent(child.props.children);
  return [{value: String(child.props.value ?? label), label, disabled: child.props.disabled}];
 });
}

/** Retains existing option labels, stored values, and configuration change handlers. */
export function AutocompleteSelect({children, value, onChange, 'aria-label': label, ...props}: {
 children: ReactNode; value: string | number; onChange: (event: {target: {value: string}}) => void;
 'aria-label'?: string; id?: string; disabled?: boolean; className?: string;
}) {
 return <Autocomplete {...props} label={label} value={String(value)} options={readOptions(children)} allowCustom={false} onChange={next => onChange({target: {value: next}})}/>;
}
