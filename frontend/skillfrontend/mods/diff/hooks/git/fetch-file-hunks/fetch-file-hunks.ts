import Argv from '../argv'
import { EMPTY_FILE_HUNKS } from '../empty-file-hunks'
import Parse from '../parse'
import type Types from '../types'
import { isLastOfDiff } from './is-last-of-diff'
import { withClosingLine } from './with-closing-line'

/**
 * One file's hunks against the base its row was read against, so body and
 * counts agree, by literal pathspec, as the built-in panel reads hunks.
 *
 * An untracked, binary or renamed row (the built-in shows a rename's
 * counts, never its body), or on an unborn HEAD a file edited after
 * staging, answers no hunks; each file but the last, a closing empty row.
 *
 * @param run runs git against the pinned repository
 * @param data the fetch the row belongs to
 * @param file the row
 * @returns the parsed body, or null when git failed
 */
export async function fetchFileHunks(
  run: Types.GitRun,
  data: Types.DiffData,
  file: Types.FileStat,
): Promise<Types.FileHunks | null> {
  const hasNoBody =
    file.isUntracked ||
    file.isBinary ||
    file.renamedFrom !== null ||
    data.stalePaths.includes(file.path)

  if (hasNoBody) {
    return EMPTY_FILE_HUNKS
  }

  const { exitCode, stdout } = await run([
    '--literal-pathspecs',
    ...Argv.DIFF_LEADING_ARGS,
    data.baseRef,
    '--',
    file.path,
  ])

  if (exitCode !== 0) {
    return null
  }

  const body = Parse.parseFileDiff(stdout)

  return isLastOfDiff(data, file) ? body : withClosingLine(body)
}
