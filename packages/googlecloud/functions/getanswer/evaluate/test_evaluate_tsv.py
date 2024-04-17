"""
usage: 'deepeval test run test_evaluate_gold_dataset.py'

Reads test queries from tsv file inputted by user, gets the sawt responses, evaluates the responses according to several metrics as implemented by the deepeval library <https://github.com/confident-ai/deepeval/> and gpt-3.5-turbo-1106

This file can contain be a gold data set with feature 'expected response', a list of queries without expected responses, or a mix of both. 
Queries with specified expected responses will be eveluated on 2 more metrics than queries without expected responses.

Test results and hyperparameters used by current model are logged in deepeval login.

"""
import pytest
import deepeval
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.metrics import AnswerRelevancyMetric, BiasMetric, ContextualRelevancyMetric, FaithfulnessMetric, GEval, ContextualPrecisionMetric, ContextualRecallMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from inquirer import route_question
from helper import get_dbs
from inquirer import INDEPTH_RESPONSE_LLM, INDEPTH_RESPONSE_PROMPT_TEMPLATE, INDEPTH_RESPONSE_K
from api import RESPONSE_TYPE_DEPTH

logger = logging.getLogger(__name__)


# model to use for evaluating responses
MODEL = 'gpt-3.5-turbo-1106'


def get_test_cases():
    """
    Run sawt on all test queries and create LLMTestCases for each.
    """
    test_cases = []
    db_fc, db_cj, db_pdf, db_pc, db_news, voting_roll_df = get_dbs()

    tsv_file_name = input("Enter the name or path of your tsv file of queries (ex: queries.tsv):")
    if not os.path.exists(tsv_file_name):
        print("\nThe file ", tsv_file_name, " doesn't exist, check the path or name.")
        sys.exit()
    logger.info('generating answers to all test queries...')

    with open(tsv_file_name) as file:
        next(file)
        for row in file:
            row_obj = row.strip().split('\t')
            if len(row_obj) == 1:
                query = row_obj[0]
                expected_output = ''
            else:
                query, expected_output = row_obj

            actual_output, retrieval_context = route_question(
                voting_roll_df,
                db_fc,
                db_cj,
                db_pdf,
                db_pc,
                db_news,
                query,
                RESPONSE_TYPE_DEPTH,
                k=5,
                return_context=True
            )
            # get single string for text response
            actual_output = ' '.join(i['response'] for i in actual_output['responses'])    
            test_cases.append(LLMTestCase(input=query, actual_output=actual_output, expected_output=expected_output, retrieval_context=[retrieval_context]))

    return EvaluationDataset(test_cases=test_cases)

dataset = get_test_cases()


@pytest.mark.parametrize(
    "test_case",
    dataset,
)
def test_dataset(test_case: LLMTestCase):
    #require expected_output
    contextual_precision = ContextualPrecisionMetric(threshold=0.2, model=MODEL)
    contextual_recall = ContextualRecallMetric(threshold=0.2, model=MODEL)
    
    #don't require expected_output
    answer_relevancy = AnswerRelevancyMetric(threshold=0.2, model=MODEL)
    bias = BiasMetric(threshold=0.5, model=MODEL)
    contextual_relevancy = ContextualRelevancyMetric(threshold=0.7, include_reason=True, model=MODEL)
    faithfulness = FaithfulnessMetric(threshold=0.7, include_reason=True, model=MODEL)
   
    readability = GEval(name="Readability",
        criteria="Determine whether the text in 'actual output' is easy to read for those with a high school reading level.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=MODEL)


    punctuation = GEval(name="Punctuation",
        criteria="Determine whether the text in 'actual output' has proper punctuation.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=MODEL)
   
    opinions = GEval(name="Number of Opinions",
        criteria="Determine whether the text in 'actual output' expresses more than one opinion on the topic of the query.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=MODEL)

    assert_test(test_case, [contextual_recall, contextual_precision, answer_relevancy, bias, contextual_relevancy, faithfulness,readability, punctuation, opinions])


# Log hyperparameters so we can compare across different test runs in deepeval login
@deepeval.log_hyperparameters(model=INDEPTH_RESPONSE_LLM.model_name, prompt_template=INDEPTH_RESPONSE_PROMPT_TEMPLATE.template)
def hyperparameters():
    return {'k': INDEPTH_RESPONSE_K}

