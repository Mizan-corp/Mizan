import type {PresetKind,TemplateKind} from '../../nativePresets';
/** A page starter is one body recipe, not a multi-page site kit or installed package. */
export const pageRecipes:Record<TemplateKind,readonly PresetKind[]>={studio:['hero','story','features','contact'],service:['hero','features','quote','contact'],editorial:['hero','story','quote','callout']};
