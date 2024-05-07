# CoE-SQL

This is the project containing the source code for the NAACL2024 paper [*CoE-SQL: In-Context Learning for Multi-Turn Text-to-SQL with Chain-of-Editions*](https://arxiv.org/abs/2405.02712) in **NAACL 2024 main conference**. If you find it useful, please cite our work.

    @misc{zhang2024coesql,
          title={CoE-SQL: In-Context Learning for Multi-Turn Text-to-SQL with Chain-of-Editions}, 
          author={Hanchong Zhang and Ruisheng Cao and Hongshen Xu and Lu Chen and Kai Yu},
          year={2024},
          eprint={2405.02712},
          archivePrefix={arXiv},
          primaryClass={cs.CL}
    }

## Run CoE-SQL

1. Create the `data` directory and move the downloaded datasets into this directory. Here is the example of the directory structure.

```
data
├── cosql
│   ├── database (directory)
│   ├── database-testsuite (directory)
│   ├── dev.json
│   ├── tables.json
│   └── train.json
└── sparc
    ├── database (directory)
    ├── database-testsuite (directory)
    ├── dev.json
    ├── tables.json
    └── train.json
```

2. Run `edit.py` to automatically generate the chain-of-editions for all examples in the train set. Here are two examples.

```
python edit.py --dataset sparc --max_len 4
python edit.py --dataset cosql --max_len 3
```

3. Run `main.py` to run CoE-SQL on the dev set. Here are two examples.

```
python main.py --dataset sparc --coe
python main.py --dataset cosql --coe
```
