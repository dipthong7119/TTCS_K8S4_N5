import type Git from '../git'
import Limits from '../limits'
import PaneState from '../pane-state'

/**
 * The files whose bodies the pane draws now, in drawing order: the listed
 * session rows, then the pre-session rows while their section is open.
 *
 * Past PRE_SESSION_BODY_CAP pre-session files only their legend shows, so
 * none of their bodies is wanted.
 *
 * @param model the pane's state: its fetch and its two toggles
 * @returns the rows, none without a fetch
 */
export function drawnFilesOf(
  model: Pick<
    PaneState.PaneModel,
    'data' | 'isNoiseShown' | 'isPreSessionShown'
  >,
): readonly Git.FileStat[] {
  const partition = PaneState.partitionOf(
    model.data?.files ?? [],
    model.isNoiseShown ? 'shown' : 'hidden',
  )

  const isBodied =
    model.isPreSessionShown &&
    partition.preSession.length <= Limits.PRE_SESSION_BODY_CAP

  return [...partition.shown, ...(isBodied ? partition.preSession : [])]
}
