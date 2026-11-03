// SpendLens — minimal tweaks panel (dark mode toggle only)
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  const setTweak = React.useCallback((key, val) => {
    setValues(prev => ({ ...prev, [key]: val }));
  }, []);
  return [values, setTweak];
}

function TweaksPanel({ children }) { return null; } // hidden in production
function TweakSection({ label, children }) { return null; }
function TweakToggle({ label, value, onChange }) { return null; }

Object.assign(window, { useTweaks, TweaksPanel, TweakSection, TweakToggle });
