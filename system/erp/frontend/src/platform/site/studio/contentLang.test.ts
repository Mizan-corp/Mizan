import { describe, expect, it } from 'vitest';
import { pickContentLanguage } from './contentLang';

describe('pickContentLanguage', () => {
  it('defaults to English on first load of a bilingual page', () => {
    expect(pickContentLanguage(['en', 'ar'], 'en', true)).toBe('en');
  });
  it('falls back to Arabic on first load of an Arabic-titled page', () => {
    expect(pickContentLanguage(['ar'], 'en', true)).toBe('ar');
  });
  it('keeps the selected language on in-app switches', () => {
    expect(pickContentLanguage(['en', 'ar'], 'ar', false)).toBe('ar');
    expect(pickContentLanguage(['en', 'ar'], 'en', false)).toBe('en');
  });
  it('keeps Arabic on a page whose title exists only in English', () => {
    // Titles are not content: an English-only title still holds Arabic content.
    expect(pickContentLanguage(['en'], 'ar', false)).toBe('ar');
  });
});
