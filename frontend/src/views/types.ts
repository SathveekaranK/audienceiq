import type { Creator } from '@/lib/api'

/** Props every view receives. */
export interface ViewProps {
  creator: Creator
  onChanged: () => void
  notify: (message: string, tone?: 'success' | 'danger') => void
  /** Switch the workspace to a different channel. */
  selectCreator: (creatorId: number) => void
}
