import os
import numpy as np

from argparse import ArgumentParser, Namespace
from pathlib import Path

from .utils import mkdir, get_project_names, get_project_vectors
from .data_processing import ProcessedData, assign_clusters, compute_vectors, normalize_vectors, build_similarity_index, \
    get_top_supertokens
from tokenizer.topic_dynamics.run import main as run_tokenizer


def tokenize(input_file: str, output_dir: str, batches: int, force: bool) -> None:
    """
    :param input_file: input file with a list of links to projects for analysis.
    :param output_dir: directory to store data during tokenizing.
    :param batches: size of project batches that are saved to one file.
    :param force: if True, tokenizer will re-run (even if results have been stored previously).
    :return: None.
    """

    mkdir(output_dir)
    try:
        if not force and len(ProcessedData(Path(output_dir)).indices()) > 0:
            print(f'Found tokenizer output in {output_dir}.\n'
                  f'If you want to re-run tokenizer, pass --force flag.')
            return
    except ValueError:
        pass

    if not os.path.exists(input_file):
        raise ValueError(f'Input file {input_file} does not exist!')

    tokenizer_args = Namespace(input=input_file, output=output_dir, batches=batches)
    print(f'Running tokenizer on repos listed in {input_file}')
    run_tokenizer(tokenizer_args)


def vectorize(processed_data: ProcessedData, force: bool) -> None:
    """
    Compute numerical representations for repositories processed by tokenizer.
    :param processed_data: wrapper for directory where tokenizer stored extracted data about tokens in repositories.
    :param force: if True, vectorization will re-run (even if results have been stored previously).
    :return: None.
    """
    if not force and processed_data.has_stored_repo_names() and processed_data.has_stored_repo_vectors():
        print(f'Found precomputed vectors in {processed_data.folder()}.\n'
              f'If you wan to re-run vector computation, pass --force flag.')
        return

    all_repo_names = []
    all_vectors_list = []

    print(f'Found {len(processed_data.indices())} batches with tokenized data.')
    for ind in processed_data.indices():
        vocab = processed_data.load_tokens_vocab(ind)
        tokens_to_clusters = assign_clusters(vocab)
        docword = processed_data.load_docword(ind)
        repo_names, vectors = compute_vectors(docword, tokens_to_clusters)
        all_repo_names += repo_names
        all_vectors_list.append(vectors)

    all_vectors = np.concatenate(all_vectors_list)
    processed_data.store_repo_names(all_repo_names)
    processed_data.store_repo_vectors(all_vectors)


def analyze(processed_data: ProcessedData, min_stars: int, closest: int, explain: bool) -> None:
    repo_names = processed_data.load_repo_names()
    repo_vectors = normalize_vectors(processed_data.load_repo_vectors())

    project_names = get_project_names(min_stars)
    project_embed = get_project_vectors(min_stars)

    index = build_similarity_index(project_embed)

    distances, indices = index.search(repo_vectors, closest)

    for repo_name, repo_vector, dist_vector, idx in zip(repo_names, repo_vectors, distances, indices):
        print()
        print('-----------------------')
        print(f'Top picks for {repo_name}')
        for ind, dist in zip(idx, dist_vector):
            print(f'https://github.com/{project_names[ind]} | {dist:.4f}')

            if explain:
                top_supertokens = get_top_supertokens(repo_vector, index, int(ind))
                print('Top supertokens:')
                print('\n'.join([f'{dim} : {product:.2f}' for dim, product in top_supertokens]))
                print()

        print('-----------------------')
        print()



if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", required=True,
                        help="Full path to the input file with a list of links to GitHub.")
    parser.add_argument("-o", "--output", required=True,
                        help="Full path to the directory for storing extracted data.")
    parser.add_argument("-b", "--batches", default=100, type=int,
                        help="The size of the batch of projects that are saved to one file.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="If passed, all stages will be re-run, otherwise stored data will be used.")
    parser.add_argument("-s", "--min_stars", default=100, type=int,
                        help="Find similar projects among projects with at least min_stars stars. "
                             "Valid options are 0, 1, 10, 50, 100.")
    parser.add_argument("-k", "--closest", default=10, type=int,
                        help="Number of closest repositories to find.")
    parser.add_argument("-e", "--explain", action="store_true",
                        help="If passed, the output will contain top super-tokens matched with each repository.")
    args = parser.parse_args()

    tokenize(args.input, args.output, args.batches, args.force)
    processed_data = ProcessedData(Path(args.output))
    vectorize(processed_data, args.force)
    analyze(processed_data, args.min_stars, args.closest, args.explain)
