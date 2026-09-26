import {useEffect, useRef} from 'react';
import {Search, SlidersHorizontal, ChevronDown, Heart, Star, X} from 'lucide-react';
import {t} from './i18n';

export function SongFilters({query,setQuery,tag,setTag,rating,setRating,favorites,setFavorites}: {
  query:string;setQuery:(value:string)=>void;tag:string;setTag:(value:string)=>void;
  rating:string;setRating:(value:string)=>void;favorites:boolean;setFavorites:(value:boolean)=>void;
}) {
  const details=useRef<HTMLDetailsElement>(null);
  const active=Number(tag!=='*')+Number(rating!=='*')+Number(favorites);
  useEffect(()=>{
    const outside=(e:PointerEvent)=>{if(!details.current?.contains(e.target as Node))details.current?.removeAttribute('open');};
    const escape=(e:KeyboardEvent)=>{if(e.key==='Escape'&&details.current?.open){details.current.open=false;details.current.querySelector('summary')?.focus();}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};
  },[]);
  return <div className="song-filter-toolbar"><div className="song-search"><Search size={16}/><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder={t('搜索歌名、风格')} aria-label={t('搜索歌名、风格')}/>{query&&<button type="button" aria-label={t('清除搜索')} title={t('清除搜索')} onClick={()=>setQuery('')}><X size={14}/></button>}</div><details ref={details} className="song-filter-dropdown"><summary className={active?'has-filters':''}><SlidersHorizontal size={16}/>{t('筛选')}{active>0&&<span className="filter-count">{active}</span>}<ChevronDown size={15}/></summary><div className="song-filter-popover"><div className="filter-popover-heading"><strong>{t('筛选')}</strong><button type="button" className="text-button" disabled={!active} onClick={()=>{setTag('*');setRating('*');setFavorites(false);}}>{t('重置筛选')}</button></div><div className="filter-track-types"><span>{t('音轨类型')}</span><div className="filter-track-tags" role="group" aria-label={t('音轨类型')}>{[['original',t('原曲')],['vocals',t('人声')],['instrumental',t('伴奏')]].map(([value,label])=><button key={value} type="button" className={'filter-tag '+(tag===value?'selected':'')} aria-pressed={tag===value} onClick={()=>setTag(tag===value?'*':value)}>{label}</button>)}</div></div><div className="filter-rating"><span>{t('星级筛选')}</span><div className="filter-stars" role="group" aria-label={t('星级筛选')}>{[1,2,3,4,5].map(n=><button key={n} type="button" className={n<=Number(rating)?'selected':''} aria-pressed={rating===String(n)} aria-label={t('{0} 星',n)} title={t('{0} 星',n)} onClick={()=>setRating(rating===String(n)?'*':String(n))}><Star size={24} fill={n<=Number(rating)?'currentColor':'none'}/></button>)}</div></div><div className="filter-favorite-tags"><button type="button" className={'filter-tag favorite-tag '+(favorites?'selected':'')} aria-pressed={favorites} onClick={()=>setFavorites(!favorites)}><Heart size={15} fill={favorites?'currentColor':'none'}/>{t('仅看收藏')}</button></div></div></details></div>;
}
