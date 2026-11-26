// Arabic display names for built-in library assets. Data ids and English source
// strings stay unchanged; these maps are presentation-only for the Arabic studio UI.
export const categoryAr: Record<string, string> = {
  'Hero sections': 'أقسام البداية',
  'Stories': 'حكايات',
  'Features': 'مميزات',
  'Feedback': 'آراء',
  'Pricing': 'أسعار',
  'FAQ': 'أسئلة شائعة',
  'Galleries': 'معارض',
  'Contact': 'تواصل',
  'Calls to action': 'دعوات لإجراء',
  'Catalog': 'كتالوج',
  'Teams': 'فرق',
};
export const blockAr: Record<string, { n: string; d: string }> = {
  product_card: { n: 'قالب كارت منتج', d: 'عنوان ونص سعر عرض وصورة قابلين للتعديل. وصّل العمود لوحده، بموافقة موديول صريحة.' },
  hero: { n: 'مقدمة + صورة', d: 'عنوان رئيسي ومقدمة وزر ورسمة قابلة للتعديل.' },
  story: { n: 'صورة + حكاية', d: 'حكاية على عمودين والرسمة الأول.' },
  callout: { n: 'دعوة لإجراء', d: 'رسالة مركزة وخطوة تالية واحدة واضحة.' },
  features: { n: 'تلات مميزات', d: 'تلات أعمدة قابلة للتعديل لأقوى أفكارك.' },
  quote: { n: 'اقتباس مميز', d: 'اقتباس في النص مع نسبة لصاحبه.' },
  contact: { n: 'دعوة تواصل', d: 'عنوان تواصل ولينك صفحة تواصل قابل للتعديل.' },
  hero_center: { n: 'مقدمة في النص', d: 'عنوان رئيسي في النص ورسمة تحته.' },
  feedback_cards: { n: 'حكايتين عملاء', d: 'كارتين رأي قابلين للتعديل. بدّل كل الاقتباسات التجريبية.' },
  features_split: { n: 'ميزة + رسمة', d: 'رسمة جنب حكاية ميزة مركزة.' },
  pricing_cards: { n: 'تلات خطط', d: 'نصوص خطط قابلة للتعديل ولينكات استفسار. مفيش توصيل دفع.' },
  pricing_simple: { n: 'عرض واحد', d: 'عرض واحد ولينك تواصل. الأسعار التجريبية مش أسعار حقيقية.' },
  faq_list: { n: 'أسئلة وأجوبة', d: 'أجوبة قابلة للقراءة والتعديل، ظاهرة دايمًا، من غير سلوك أكورديون.' },
  faq_columns: { n: 'أسئلة على عمودين', d: 'أسئلة وأجوبة جنب بعض، من غير سلوك أكورديون.' },
  contact_split: { n: 'تواصل + رسمة', d: 'رسالة ولينك صفحة تواصل جنب رسمة.' },
  gallery_pair: { n: 'معرض صورتين', d: 'صورتين ديكور قابلين للتعديل. بدّلهم بميديا بتاعتك.' },
  gallery_grid: { n: 'معرض تلات صور', d: 'صف متجاوب من تلات صور قابلة للتعديل.' },
  team_pair: { n: 'قابل المؤسسين', d: 'بروفايلين برسومات وأسماء وأدوار قابلة للتعديل.' },
  team_grid: { n: 'قابل الفريق', d: 'تلات بروفايلات قابلة للتعديل. كل الأسماء نص تجريبي.' },
  category_cards: { n: 'كروت الأقسام', d: 'صف كروت أقسام: رسمة واسم ولينك تصفح لكل قسم. الرسومات واللينكات تجريبية لحد ما تحط بتاعتك.' },
  check_list: { n: 'قائمة علامات صح', d: 'قائمة نقطية بعلامات صح للعناصر أو الخطوات أو المميزات المشمولة.' },
  icon_list: { n: 'قائمة أيقونات', d: 'نقاط قصيرة، كل واحدة بأيقونة بسيطة تختارها من مجموعة مدمجة.' },
  contact_form: { n: 'نموذج تواصل', d: 'نموذج تواصل شغال: الزوار يبعتوا رسالة من الصفحة المنشورة، وتقرا كل رسالة في تاب الموقع. الإيميل والرسالة مطلوبين دايمًا؛ الاسم والتليفون سويتشات.' },
};
export const templateAr: Record<string, { n: string; d: string }> = {
  studio: { n: 'استوديو مستقل', d: 'مقدمة وحكاية استوديو وتلات قيم وقسم تواصل.' },
  service: { n: 'خدمات إبداعية', d: 'مقدمة خدمة وفوائد ورأي عميل ودعوة استفسار.' },
  editorial: { n: 'مجلة وأفكار', d: 'مقدمة نشرة وقصة مميزة واقتباس ودعوة قراءة.' },
};
export function blocksWord(n: number): string {
  if (n === 1) return 'بلوك واحد';
  if (n === 2) return 'بلوكين';
  if (n >= 3 && n <= 10) return `${n} بلوكات`;
  return `${n} بلوك`;
}

import {getUILang} from '../uiStrings';
const arUI=()=>getUILang()==='ar';
export const blockName=(id:string,en:string)=>arUI()?(blockAr[id]?.n??en):en;
export const blockDesc=(id:string,en:string)=>arUI()?(blockAr[id]?.d??en):en;
export const templateName=(id:string,en:string)=>arUI()?(templateAr[id]?.n??en):en;
export const templateDesc=(id:string,en:string)=>arUI()?(templateAr[id]?.d??en):en;
export const categoryName=(c:string)=>arUI()?(categoryAr[c]??c):c;
