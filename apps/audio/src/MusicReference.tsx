import {ReferenceMedia} from './ReferenceMedia';
import {t} from './i18n';
export function MusicReference(props: Parameters<typeof ReferenceMedia>[0]) {
 return <ReferenceMedia {...props} help={t('可选：提取参考音频的旋律或和弦，结合下方歌词和风格重新生成。最长 15 分钟，不会续接原曲或复制原音色。')}/>;
}
