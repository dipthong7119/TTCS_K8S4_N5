import type Types from '../types'
import { TRANSIENT_STATE_FILES } from './transient-state-files'

/**
 * Whether the repository is mid-merge, mid-rebase, mid-cherry-pick or
 * mid-revert, from one listing of the git directory.
 *
 * A state file counts only as a real file; a symbolic link by that name is
 * never touched.
 *
 * @param entryKindsOf the host's directory listing
 * @param gitDir the repository's own git directory, absolute
 * @returns whether any of TRANSIENT_STATE_FILES is present as a file
 */
export async function isTransient(
  entryKindsOf: Types.GitDeps['entryKindsOf'],
  gitDir: string,
): Promise<boolean> {
  const entries = await entryKindsOf(gitDir)

  return TRANSIENT_STATE_FILES.some(file => entries?.get(file) === 'file')
}
