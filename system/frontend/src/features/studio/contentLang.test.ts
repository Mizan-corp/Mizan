import { describe, expect, it } from 'vitest';
import { pickContentLanguage } from './contentLang';

describe('pickContentLanguage', () => {
  it('keeps the selected language when the target page supports it', () => {
    expect(pickContentLanguage(['en', 'ar'], 'ar')).toBe('ar');
    expect(pickContentLanguage(['en', 'ar'], 'en')).toBe('en');
  });
  it('falls back to English only when the previous selection is unavailable', () => {
    expect(pickContentLanguage(['en'], 'ar')).toBe('en');
  });
  it('falls back to Arabic on an Arabic-only page', () => {
    expect(pickContentLanguage(['ar'], 'en')).toBe('ar');
  });
  it('defaults to English on first load of a bilingual page', () => {
    expect(pickContentLanguage(['en', 'ar'], 'en')).toBe('en');
  });
});
