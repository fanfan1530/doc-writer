import { useEffect } from 'react';
import { useAppContext } from '../context/AppContext';

/** 自动从共享笔录填充输入框（仅首次挂载时）。 */
export function useSharedTranscript(onFill: (text: string) => void, skipIf: boolean = false) {
  const { sharedTranscript } = useAppContext();

  useEffect(() => {
    if (skipIf || !sharedTranscript) return;
    onFill(sharedTranscript.text);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
