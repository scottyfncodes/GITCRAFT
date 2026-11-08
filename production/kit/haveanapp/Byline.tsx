/**
 * HaveAnApp attribution (GITCRAFT standard; reference: HangarBook's Brand.tsx `Byline`).
 * The app's name stays the hero; this is the maker's quiet signature. Style with byline.css,
 * or the app's own design system, keeping it small, muted and theme-aware.
 */
export const COMPANY_NAME = 'HaveAnApp';
/** The official HaveAnApp website (production/kit/haveanapp/attribution.json). Never HaveAnAppHQ (Instagram only). */
export const COMPANY_URL: string | null = 'https://haveanapp.com';

export function Byline({ appName }: { appName?: string }) {
  const by = COMPANY_URL
    ? <a className="haveanapp-byline__by" href={COMPANY_URL} rel="noopener" target="_blank">by {COMPANY_NAME}</a>
    : <span className="haveanapp-byline__by">by {COMPANY_NAME}</span>;
  return <p className="haveanapp-byline" data-haveanapp="">{appName ? <>{appName} </> : null}{by}</p>;
}
