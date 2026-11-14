/** Where the visitor's theme choice is remembered ("system", "light" or "dark"). */
export const THEME_STORAGE_KEY = "theme";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/**
 * Runs inline in <head> before first paint, so a dark-mode visitor never sees
 * a flash of the light theme. It resolves the stored preference ("system"
 * when unset or unreadable) to data-theme="light|dark" on <html> and records
 * the preference itself in data-theme-pref for the switch to read.
 */
export const themeInitScript = `(function(){try{var d=document.documentElement,p=null;try{p=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)})}catch(e){}if(p!=="light"&&p!=="dark")p="system";var r=p==="system"?(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):p;d.setAttribute("data-theme",r);d.setAttribute("data-theme-pref",p)}catch(e){}})();`;
