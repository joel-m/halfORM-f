create user halftest password 'halftest';
create database halftest owner halftest;

\c halftest halftest

create schema actor;
create table actor.person(
    first_name text,
    last_name text,
    birth_date date,
    primary key(first_name, last_name, birth_date)
);

create schema blog;
create sequence blog.id_post;
create table blog.post(
    id int default nextval('blog.id_post') unique not null,
    title text,
    content text,
    a_first_name text,
    a_last_name text,
    a_birth_date date,
    primary key(id)
);
alter table blog.post add constraint "author"
    foreign key(a_first_name, a_last_name, a_birth_date)
    references actor.person(first_name, last_name, birth_date)
	on update cascade on delete cascade;

create sequence blog.id_comment;
create table blog.comment(
    id int default nextval('blog.id_comment') unique not null,
    content text,
    id_post int,
    a_first_name text,
    a_last_name text,
    a_birth_date date,
    primary key(id)
);
alter table blog.comment add constraint "author"
    foreign key(a_first_name, a_last_name, a_birth_date)
    references actor.person(first_name, last_name, birth_date)
	on update cascade on delete cascade;
alter table blog.comment add constraint "post"
    foreign key(id_post)
    references blog.post
	on update cascade on delete cascade;