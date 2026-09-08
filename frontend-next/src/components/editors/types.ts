import type { useSectionForm } from '@/hooks/useSectionForm';
import type { SectionContent } from '@/types/cv';

export interface EditorProps<T extends SectionContent> {
  form: ReturnType<typeof useSectionForm<T>>;
}
